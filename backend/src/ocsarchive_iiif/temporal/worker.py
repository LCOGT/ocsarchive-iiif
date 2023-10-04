from __future__ import annotations

import logging
import asyncio
import multiprocessing
import contextlib

from uuid import uuid4
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor

import httpx
import boto3
import temporalio.api.workflowservice.v1 as wfsvcv1

from watchfiles import awatch
from temporalio.worker import Worker
from google.protobuf.duration_pb2 import Duration

from ..config import validate_app_config
from .client import connect_client
from .activities.activities import Activities
from .workflows.workflows import (
    GetFrameDimensions,
    DownloadFrameFile,
    CreateImage,
)

async def run_worker():
    """
    Start-up the worker.
    """
    # Parse config/env vars
    app_config = validate_app_config()

    # Configure logging
    logging.basicConfig(
        level=logging.getLevelName(app_config.temporal.worker.log_level.upper())
    )

    # Connect to the Temporal API server
    client = await connect_client()

    # Try to create the namespace (it may already exisit)
    # Ideally this should be done once by an admin
    try:
        retention_period = Duration()
        retention_period.FromTimedelta(td=timedelta(days=3))

        await client.workflow_service.register_namespace(
            req=wfsvcv1.RegisterNamespaceRequest(
                namespace=app_config.temporal.namespace,
                workflow_execution_retention_period=retention_period,
            )
        )
    except Exception as e:
        logging.info("did not create namespace: %s", e)

    # Workflows that this worker can handle
    wfs = [
        GetFrameDimensions,
        DownloadFrameFile,
        CreateImage,
    ]


    http_client = httpx.AsyncClient()

    s3_client = boto3.client(
        "s3",
        endpoint_url=str(app_config.s3.endpoint_url),
        aws_access_key_id=app_config.s3.access_key_id,
        aws_secret_access_key=app_config.s3.secret_access_key.get_secret_value(),
        verify=app_config.s3.verify_tls,
    )

    acts = Activities(
      temporal_client=client,
      http_client=http_client,
      app_config=app_config,
      s3_client=s3_client
    )

    # Activities that this worker can handle
    act_handlers = [
        acts.get_worker_specific_task_queue,
        acts.find_best_worker,
        acts.download_frame_file_with_workflow,
        acts.download_frame_file,
        acts.get_hdu_dimensions,
        acts.delete_file,
        acts.create_image_file,
        acts.start_s3_multipart_upload,
        acts.upload_s3_part,
        acts.finish_s3_multipart_upload,
        acts.abort_s3_multipart_upload,
    ]

    # Theadpool for non "async def" actvities
    theadpool_exec = ThreadPoolExecutor(max_workers=20)

    # Using the Worker-Specific Task Queues pattern to achieve locality for
    # multiple activities (if needed).
    # https://github.com/temporalio/samples-typescript/tree/main/worker-specific-task-queues

    # Each process runs 2 workers.

    # One worker listens to a generic task queue
    generic_worker = Worker(
      client,
      task_queue="generic",
      workflows=wfs,
      activities=act_handlers,
      activity_executor=theadpool_exec,
    )

    # Another worker runs on a worker specific task queue.
    exclusive_worker = Worker(
      client,
      task_queue=generate_worker_specific_task_queue(),
      workflows=wfs,
      activities=act_handlers,
      activity_executor=theadpool_exec,
    )

    # And then in the Workflow, one would call the Activity, "get_worker_specific_task_queue"
    # (sent on the generic task queue so that any free worker may pick it up)
    # to get a worker's specific task queue name. And then all following
    # activities (that *must* run on the same worker) can use that queue.

    # Run them both in parallel & wait for their completion (hopefully never)
    async with asyncio.TaskGroup() as tg:
        tg.create_task(generic_worker.run())
        tg.create_task(exclusive_worker.run())

    await http_client.aclose()


def generate_worker_specific_task_queue() -> str:
    """
    Return a persistent ID for this worker.

    On first run a unique ID is generated and stored to disk. Subsequent calls
    return the same ID (assuming the disk is truly persistent). Writing to
    disk allows a worker to recover from a transient crash or restart.
    """
    app_config = validate_app_config()

    file_path = app_config.temporal.worker.working_dir / "worker-task-queue.txt"

    try:
        q = file_path.read_text()
    except FileNotFoundError:
        q = f"worker/{uuid4()}"
        file_path.write_text(q)

    return q


def reload_main_once():
    asyncio.run(run_worker())


async def amain():
    app_config = validate_app_config()

    # skip all the magic if not reloading on file change
    if not app_config.temporal.worker.reload:
        await run_worker()
        return

    # Launch a new worker in a new process on any file changes
    watch = awatch(app_config.temporal.worker.reload.path)

    print("Auto-reload enabled. Will restart worker on source changes.")
    print("Watching for changes in '%s'" % app_config.temporal.worker.reload.path)

    while True:
        p = multiprocessing.get_context("spawn").Process(target=reload_main_once)
        p.start()

        print("Started new worker in process %s" % p.pid)

        changes = await anext(watch)
        print("Detected change: %s" % changes)

        print("Terminating worker in process %s" % p.pid)
        try:
            p.terminate()
            # Give it a few seconds to shut-down gracefully
            async with asyncio.timeout(5):
                await asyncio.to_thread(lambda: p.join())
        except BaseException:
            with contextlib.suppress(BaseException):
                p.kill()

        print("Terminated worker in process %s" % p.pid)
        p.close()



def main():
    asyncio.run(amain())


if __name__ == "__main__":
    main()

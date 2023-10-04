from __future__ import annotations

import asyncio

from math import ceil
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from ..activities import activities
    from ..activities.schema import (
        FindBestWorkerInput,
        DownloadFrameFileInput,
        DownloadFrameFileOuput,
        GetHduDimensionsInput,
        CreateImageFileInput,
        PixelRegion,
        PixelSize,
        DeleteFileInput,
        StartS3MultipartUploadInput,
        UploadS3PartInput,
        UploadS3PartOutput,
        FinishS3MultipartUploadInput,
        AbortS3MultipartUploadInput,
    )
    from . import schema


@workflow.defn
class GetFrameDimensions:

    @workflow.run
    async def run(self, i: schema.GetFrameDimensionsInput) -> schema.GetFrameDimensionsOutput:
        while True:
            try:
                return await self._run(i)
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(5)
                continue

    async def _run(self, i: schema.GetFrameDimensionsInput) -> schema.GetFrameDimensionsOutput:
        w = await workflow.execute_activity_method(
            activities.Activities.find_best_worker,
            FindBestWorkerInput(frame_id=i.frame_id),
            start_to_close_timeout=timedelta(seconds=5),
        )

        f = await workflow.execute_activity_method(
            activities.Activities.download_frame_file_with_workflow,
            DownloadFrameFileInput(
                frame_id=i.frame_id,
                force_download=i.force_download,
                recheck_version=i.recheck_version,
            ),
            task_queue=w.task_queue,
            start_to_close_timeout=timedelta(minutes=5),
            schedule_to_start_timeout=timedelta(seconds=15),
            retry_policy=RetryPolicy(
                maximum_attempts=3
            ),
        )

        d = await workflow.execute_activity_method(
            activities.Activities.get_hdu_dimensions,
            GetHduDimensionsInput(
              fits_path=f.file_path,
              hdu_index=i.hdu_index,
            ),
            task_queue=w.task_queue,
            start_to_close_timeout=timedelta(seconds=10),
            schedule_to_start_timeout=timedelta(seconds=15),
            retry_policy=RetryPolicy(
                maximum_attempts=3
            ),
        )

        return schema.GetFrameDimensionsOutput(width=d.width, height=d.height)


@workflow.defn
class DownloadFrameFile:

    @workflow.run
    async def run(self, i: DownloadFrameFileInput) -> DownloadFrameFileOuput:
        f = await workflow.execute_activity_method(
            activities.Activities.download_frame_file,
            i,
            heartbeat_timeout=timedelta(seconds=10),
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
            )
        )

        return f


@workflow.defn
class CreateImage:

    @workflow.run
    async def run(self, i: schema.CreateImageInput) -> schema.CreateImageOutput:
        while True:
            try:
                return await self._run(i)
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(5)
                continue

    async def _run(self, i: schema.CreateImageInput) -> schema.CreateImageOutput:
        w = await workflow.execute_activity_method(
            activities.Activities.find_best_worker,
            FindBestWorkerInput(frame_id=i.frame_id),
            start_to_close_timeout=timedelta(seconds=5),
        )

        f = await workflow.execute_activity_method(
            activities.Activities.download_frame_file_with_workflow,
            DownloadFrameFileInput(
                frame_id=i.frame_id,
                force_download=False,
                recheck_version=False,
            ),
            task_queue=w.task_queue,
            start_to_close_timeout=timedelta(minutes=5),
            schedule_to_start_timeout=timedelta(seconds=15),
            retry_policy=RetryPolicy(
                maximum_attempts=3
            ),
        )

        pixel_region = PixelRegion(
            x=i.pixel_region.x,
            y=i.pixel_region.y,
            w=i.pixel_region.w,
            h=i.pixel_region.h,
        )

        pixel_size = PixelSize(
            width=i.pixel_size.width,
            height=i.pixel_size.height,
        )

        generated_img = await workflow.execute_activity_method(
            activities.Activities.create_image_file,
            CreateImageFileInput(
              fits_path=f.file_path,
              hdu_index=i.hdu_index,
              pixel_region=pixel_region,
              pixel_size=pixel_size,
              fmt=i.fmt,
            ),
            task_queue=w.task_queue,
            start_to_close_timeout=timedelta(seconds=30),
            schedule_to_start_timeout=timedelta(seconds=15),
            retry_policy=RetryPolicy(
                maximum_attempts=3
            ),
        )

        object_key = f"generated/{generated_img.sha256}"

        try:
            mp_upload = await workflow.execute_activity_method(
                activities.Activities.start_s3_multipart_upload,
                StartS3MultipartUploadInput(
                    object_key=object_key
                ),
                start_to_close_timeout=timedelta(seconds=3),
            )

            try:

                # 5 MB part size
                # It's the smallest S3 supports https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html
                part_size = 5 * 1024 * 1024
                part_count = ceil(generated_img.file_size / part_size)

                # Upload the parts in parallel
                async with asyncio.TaskGroup() as tg:
                    upload_tasks: list[asyncio.Task[UploadS3PartOutput]] = []

                    for part_i in range(part_count):
                        t = tg.create_task(
                            workflow.execute_activity_method(
                                activities.Activities.upload_s3_part,
                                UploadS3PartInput(
                                    file_path=generated_img.file_path,
                                    file_size=generated_img.file_size,
                                    file_offset=part_size * part_i,
                                    part_size=part_size,
                                    object_key=mp_upload.object_key,
                                    upload_id=mp_upload.upload_id,
                                    part_number=part_i + 1,
                                ),
                                task_queue=w.task_queue,
                                start_to_close_timeout=timedelta(minutes=5),
                                heartbeat_timeout=timedelta(seconds=15),
                                schedule_to_start_timeout=timedelta(seconds=15),
                                retry_policy=RetryPolicy(
                                    maximum_attempts=3
                                ),
                            )
                        )
                        upload_tasks.append(t)

                uploaded_parts = [t.result() for t in upload_tasks]

                finshed_upload = await workflow.execute_activity_method(
                    activities.Activities.finish_s3_multipart_upload,
                    FinishS3MultipartUploadInput(
                        object_key=mp_upload.object_key,
                        upload_id=mp_upload.upload_id,
                        uploaded_parts=uploaded_parts,
                    ),
                    start_to_close_timeout=timedelta(seconds=3),
                )
            except Exception:
                await workflow.execute_activity_method(
                    activities.Activities.abort_s3_multipart_upload,
                    AbortS3MultipartUploadInput(
                        object_key=mp_upload.object_key,
                        upload_id=mp_upload.upload_id,
                    ),
                    start_to_close_timeout=timedelta(seconds=5),
                )
                raise
        finally:
            await workflow.execute_activity_method(
                activities.Activities.delete_file,
                DeleteFileInput(
                    file_path=generated_img.file_path
                ),
                task_queue=w.task_queue,
                start_to_close_timeout=timedelta(seconds=5),
                schedule_to_start_timeout=timedelta(seconds=15),
                retry_policy=RetryPolicy(
                    maximum_attempts=3
                ),
            )

        return schema.CreateImageOutput(s3_object_key=finshed_upload.object_key)

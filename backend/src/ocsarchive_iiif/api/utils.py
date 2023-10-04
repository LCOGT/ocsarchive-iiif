from datetime import timedelta

import temporalio.client

from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from ..temporal.workflows import workflows



async def get_frame_dimensions(
    *,
    frame_id: str,
    hdu_index: int,
    reuse_workflow: bool,
    force_download: bool,
    recheck_version: bool,
    tc: temporalio.client.Client,
) -> workflows.schema.GetFrameDimensionsOutput:
    """
    Return frame dimensions by running a workflow on Temporal.
    """
    workflow_id = f"GetFrameDimensions:frames/{frame_id}/fits/hdus/{hdu_index}"

    # First try to get cached results
    try:
        if not reuse_workflow:
            raise Exception()
        dimensions = await tc.get_workflow_handle_for(
            workflows.GetFrameDimensions.run,
            workflow_id=workflow_id
        ).result()
    except Exception:
        # Otherwise kick off a run, if one is not already running
        if reuse_workflow:
            id_reuse_policy =  WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY
        else:
            id_reuse_policy = WorkflowIDReusePolicy.ALLOW_DUPLICATE

        # And wait for the results
        try:
            dimensions = await tc.execute_workflow(
                workflows.GetFrameDimensions.run,
                workflows.schema.GetFrameDimensionsInput(
                    frame_id=frame_id,
                    hdu_index=hdu_index,
                    force_download=force_download,
                    recheck_version=recheck_version,
                ),
                id=workflow_id,
                task_queue="generic",
                id_reuse_policy=id_reuse_policy,
                execution_timeout=timedelta(hours=1),
            )
        except WorkflowAlreadyStartedError:
              dimensions = await tc.get_workflow_handle_for(
                  workflows.GetFrameDimensions.run,
                  workflow_id=workflow_id
              ).result()

    return dimensions

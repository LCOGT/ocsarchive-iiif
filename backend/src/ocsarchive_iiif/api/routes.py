from __future__ import annotations

import asyncio

from datetime import timedelta

from pydantic import TypeAdapter
from fastapi import Request, APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from ..temporal.workflows import workflows

from .schema import (
    ImageInfoResponse,
    ImageInfoTile,
    Region,
    PixelRegion,
    Size,
    PixelSize,
    FixedWidthSize,
    FixedHeightSize,
)
from .dependencies import TemporalClient, S3Client, AppConfig
from .path_params import (
    FrameIdPathParam,
    HduIndexPathParam,
    RegionPathParam,
    SizePathParam,
    RotationPathParam,
    QualityPathParam,
    FormatPathParam,
)
from .query_params import (
    ReuseWorkflowQueryParam,
    ForceDownloadQueryParam,
    RecheckVersionQueryParam,
)
from .utils import get_frame_dimensions


router = APIRouter(tags=["iiif"])


@router.get(
    "/frames/{frame_id}/fits/hdus/{hdu_index}/info.json",
    response_model_exclude_none=True,
)
async def get_image_information(
    frame_id: FrameIdPathParam,
    hdu_index: HduIndexPathParam,
    tc: TemporalClient,
    req: Request,
    reuse_workflow: ReuseWorkflowQueryParam = True,
    force_download: ForceDownloadQueryParam = False,
    recheck_version: RecheckVersionQueryParam = False,
) -> ImageInfoResponse:
    """
    Get image information.

   <https://iiif.io/api/image/3.0/#5-image-information>
    """
    dimensions = await get_frame_dimensions(
        frame_id=frame_id,
        hdu_index=hdu_index,
        reuse_workflow=reuse_workflow,
        force_download=force_download,
        recheck_version=recheck_version,
        tc=tc,
    )

    return ImageInfoResponse(
        id_=f"{req.url.replace_query_params()}".removesuffix("/info.json"),
        width=dimensions.width,
        height=dimensions.height,

        # TODO: constrain this based on a resonable value a worker could handle
        max_width=dimensions.width,
        max_height=dimensions.height,

        # TODO: Maybe scale factors should be dynamic (based on the dimensions)
        tiles=[
          ImageInfoTile(width=512, height=512, scale_factors=list(range(1, 20))),
        ],
    )


@router.get(
    "/frames/{frame_id}/fits/hdus/{hdu_index}/{region}/{size}/{rotation}/{quality}.{format}",
    #response_class=RedirectResponse,
)
async def get_image(
    frame_id: FrameIdPathParam,
    hdu_index: HduIndexPathParam,
    region: RegionPathParam,
    size: SizePathParam,
    rotation: RotationPathParam,
    quality: QualityPathParam,
    fmt: FormatPathParam,
    tc: TemporalClient,
    s3: S3Client,
    app_config: AppConfig,
    req: Request,
    reuse_workflow: ReuseWorkflowQueryParam = True,
):
    """Get an image (or its variant).

    <https://iiif.io/api/image/3.0/#4-image-requests>
    """
    info = await get_image_information(
        frame_id=frame_id,
        hdu_index=hdu_index,
        tc=tc,
        req=req
    )

    norm_region = normalize_region(region, info)
    norm_size = normalize_size(size, norm_region, info)

    workflow_id = f"CreateImage:{frame_id}/{hdu_index}/{norm_region}/{norm_size}/{rotation}/{quality}.{fmt}"

    # Otherwise kick off a run, if one is not already running
    if reuse_workflow:
        id_reuse_policy =  WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY
    else:
        id_reuse_policy = WorkflowIDReusePolicy.ALLOW_DUPLICATE

    try:
        r = await tc.execute_workflow(
            workflows.CreateImage.run,
            workflows.schema.CreateImageInput(
                frame_id=frame_id,
                hdu_index=hdu_index,
                pixel_region=workflows.schema.PixelRegion(
                    x=norm_region.x,
                    y=norm_region.y,
                    w=norm_region.w,
                    h=norm_region.h,
                ),
                pixel_size=workflows.schema.PixelSize(
                    width=norm_size.width,
                    height=norm_size.height,
                ),
                fmt=fmt,
            ),
            id=workflow_id,
            task_queue="generic",
            id_reuse_policy=id_reuse_policy,
            execution_timeout=timedelta(days=1),
        )
    except WorkflowAlreadyStartedError:
          r = await tc.get_workflow_handle_for(
              workflows.CreateImage.run,
              workflow_id=workflow_id
          ).result()

    presigned_url = await asyncio.to_thread(
        s3.generate_presigned_url,
        "get_object",
        Params={
            "Bucket": app_config.s3.bucket,
            "Key": r.s3_object_key,
        },
        # 5 mins
        ExpiresIn=5 * 60
    )

    return RedirectResponse(presigned_url)


def normalize_region(region: RegionPathParam, info: ImageInfoResponse) -> PixelRegion:
    org = TypeAdapter(Region).validate_python(region)

    norm: PixelRegion
    if org.kind == "PixelRegion":
        norm = org

    elif org.kind == "FullRegion":
        norm = PixelRegion(x=0, y=0, w=info.width, h=info.height)

    elif org.kind == "SquareRegion":
        shorter = min(info.width, info.height)
        center_x = info.width // 2
        center_y = info.height // 2
        norm = PixelRegion(x=center_x, y=center_y, w=shorter, h=shorter)

    elif org.kind == "PercentRegion":
        x = round(info.width * org.x)
        y = round(info.height * org.y)
        w = round(info.width * org.w)
        h = round(info.height * org.h)
        norm = PixelRegion(x=x, y=y, w=w, h=h)
    else:
        assert False, region

    if norm.x > info.width or norm.y > info.height:
        raise HTTPException(status_code=400, detail="Region is entirely outside the bounds of image.")

    return norm


def normalize_size(size: SizePathParam | Size, region: PixelRegion, info: ImageInfoResponse) -> PixelSize:
    org = TypeAdapter(Size).validate_python(size)

    if org.upscaleable:
        raise HTTPException(status_code=501, detail="Upscaling not supported (yet?).")

    region_aspect = region.w / region.h

    norm: PixelSize
    if org.kind == "PixelSize":
        norm = org

    elif org.kind == "MaxSize":
        w = max(region.w, info.max_width or 0)
        h = max(region.h, info.max_height or 0)

        norm = PixelSize(upscaleable=False, width=w, height=h)

    elif org.kind == "FixedWidthSize":
        w = org.width
        h = round(org.width / region_aspect)

        norm = PixelSize(upscaleable=False, width=w, height=h)

    elif org.kind == "FixedHeightSize":
        h = org.height
        w = round(h * region_aspect)

        norm = PixelSize(upscaleable=False, width=w, height=h)

    elif org.kind == "PercentSize":
        pct = org.percent / 100
        w = round(region.w * pct)
        h = round(region.h * pct)

        norm = PixelSize(upscaleable=False, width=w, height=h)

    elif org.kind == "PreservedAspectPixelSize":
        norm_max_w = normalize_size(
            FixedWidthSize(
                upscaleable=False,
                width=min(org.width, region.w, info.max_width or 0)
            ),
            region,
            info
        )
        norm_max_h = normalize_size(
            FixedHeightSize(
                upscaleable=False,
                height=min(org.height, region.h, info.max_height or 0)
            ),
            region,
            info
        )

        if norm_max_w.width * norm_max_w.height >= norm_max_h.width * norm_max_h.width:
            norm = norm_max_w
        else:
            norm = norm_max_h

    else:
        assert False, size

    if norm.width > region.w:
        raise HTTPException(
            status_code=400,
            detail=f"Scale width {norm.width} can not be more than cropped region width {region.w}."
        )

    if norm.height > region.h:
        raise HTTPException(
            status_code=400,
            detail=f"Scale height {norm.height} can not be more than cropped region width {region.w}."
        )

    if (max_w := info.max_width) is not None and norm.width > max_w:
        raise HTTPException(
            status_code=400,
            detail=f"Scale width {norm.width} can not be more than the limit {max_w}."
        )

    if (max_h := info.max_height) is not None and norm.height > max_h:
        raise HTTPException(
            status_code=400,
            detail=f"Scale height {norm.height} can not be more than the limit {max_h}."
        )

    if (max_area := info.max_area) is not None and (area := norm.width * norm.height) > max_area:
        raise HTTPException(
            status_code=400,
            detail=f"Scale area (width x height) {area} can not be more than the limit {max_area}."
        )

    return norm

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class GetFrameDimensionsInput:
    frame_id: str
    hdu_index: int
    force_download: bool
    recheck_version: bool


@dataclass(kw_only=True)
class GetFrameDimensionsOutput:
    width: int
    height: int

@dataclass(kw_only=True)
class PixelRegion:
    x: int
    y: int
    w: int
    h: int


@dataclass(kw_only=True)
class PixelSize:
    width: int
    height: int

@dataclass(kw_only=True)
class CreateImageInput:
    frame_id: str
    hdu_index: int

    pixel_region: PixelRegion
    pixel_size: PixelSize
    fmt: str


@dataclass(kw_only=True)
class CreateImageOutput:
    s3_object_key: str

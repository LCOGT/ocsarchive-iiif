from __future__ import annotations

from dataclasses import dataclass

@dataclass(kw_only=True)
class AbortS3MultipartUploadInput:
    object_key: str
    upload_id: str

@dataclass(kw_only=True)
class FinishS3MultipartUploadInput:
    object_key: str
    upload_id: str
    uploaded_parts: list[UploadS3PartOutput]

@dataclass(kw_only=True)
class FinishS3MultipartUploadOutput:
    object_key: str

@dataclass(kw_only=True)
class UploadS3PartInput:
    file_path: str
    file_size: int
    file_offset: int
    part_size: int
    object_key: str
    upload_id: str
    part_number: int

@dataclass(kw_only=True)
class UploadS3PartOutput:
    etag: str
    part_number: int

@dataclass(kw_only=True)
class StartS3MultipartUploadInput:
    object_key: str

@dataclass(kw_only=True)
class StartS3MultipartUploadOutput:
    upload_id: str
    object_key: str

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
class CreateImageFileInput:
    fits_path: str
    hdu_index: int

    pixel_region: PixelRegion
    pixel_size: PixelSize
    fmt: str


@dataclass(kw_only=True)
class CreateImageFileOutput:
    file_path: str
    sha256: str
    file_size: int


@dataclass(kw_only=True)
class GetHduDimensionsInput:
    fits_path: str
    hdu_index: int


@dataclass(kw_only=True)
class GetHduDimensionsOutput:
    width: int
    height: int


@dataclass(kw_only=True)
class DownloadFrameFileInput:
    frame_id: str
    force_download: bool
    recheck_version: bool


@dataclass(kw_only=True)
class DownloadFrameFileOuput:
    file_path: str
    cached: bool


@dataclass(kw_only=True)
class DeleteFileInput:
    file_path: str


@dataclass(kw_only=True)
class GetWorkerSpecificTaskQueueOutput:
    name: str


@dataclass(kw_only=True)
class FindBestWorkerInput:
    frame_id: str


@dataclass(kw_only=True)
class FindBestWorkerOutput:
    task_queue: str

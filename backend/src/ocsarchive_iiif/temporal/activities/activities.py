from __future__ import annotations

import asyncio
import tempfile
import os

from dataclasses import dataclass
from hashlib import sha256, file_digest
from base64 import urlsafe_b64encode
from pathlib import Path
from contextlib import suppress

import aiofiles
import aiofiles.os
import httpx
import temporalio.client

from temporalio import activity
from temporalio.exceptions import ApplicationError, WorkflowAlreadyStartedError
from astropy.io import fits
from astropy.visualization import ZScaleInterval
from PIL import Image
from mypy_boto3_s3.client import S3Client

from ...config import AppConfig
from ..workflows import workflows

from .schema import (
    GetWorkerSpecificTaskQueueOutput,
    FindBestWorkerInput,
    FindBestWorkerOutput,
    DownloadFrameFileInput,
    DownloadFrameFileOuput,
    DeleteFileInput,
    GetHduDimensionsInput,
    GetHduDimensionsOutput,
    CreateImageFileInput,
    CreateImageFileOutput,
    StartS3MultipartUploadInput,
    StartS3MultipartUploadOutput,
    UploadS3PartInput,
    UploadS3PartOutput,
    FinishS3MultipartUploadInput,
    FinishS3MultipartUploadOutput,
    AbortS3MultipartUploadInput,
)


@dataclass(kw_only=True)
class Activities:
      http_client: httpx.AsyncClient

      app_config: AppConfig

      temporal_client: temporalio.client.Client

      s3_client: S3Client

      @activity.defn
      async def get_worker_specific_task_queue(self) -> GetWorkerSpecificTaskQueueOutput:
          """
          Return the task queue exclusively associated with this worker process.

          Useful for running a set of activities that need access to shared
          resources (e.g. disk, memory, etc) across a workflow.
          """
          file_path = self.app_config.temporal.worker.working_dir / "worker-task-queue.txt"
          async with aiofiles.open(file_path) as f:
              q = await f.read()

          return GetWorkerSpecificTaskQueueOutput(name=q)

      @activity.defn
      async def find_best_worker(self, i: FindBestWorkerInput) -> FindBestWorkerOutput:
          # TODO: figure out which worker(s) already has/have the frame downloaded
          # and pick one of those.
          # Perhaps also ask another worker (ones that don't already have it)
          # to preemtively download it for load-balacing

          # dumbest option: just return this worker's queue
          r = await self.get_worker_specific_task_queue()
          wq = r.name

          return FindBestWorkerOutput(task_queue=wq)

      @activity.defn
      async def download_frame_file_with_workflow(self, i: DownloadFrameFileInput) -> DownloadFrameFileOuput:
          task_queue = activity.info().task_queue
          workflow_id = f"DownloadFrameFile:frames/{i.frame_id}/{task_queue}"
          try:
              h = await self.temporal_client.start_workflow(
                  workflows.DownloadFrameFile.run,
                  DownloadFrameFileInput(
                      frame_id=i.frame_id,
                      force_download=i.force_download,
                      recheck_version=i.recheck_version,
                  ),
                  id=workflow_id,
                  task_queue=task_queue,
              )
          except WorkflowAlreadyStartedError:
              h = self.temporal_client.get_workflow_handle_for(
                  workflows.DownloadFrameFile.run,
                  workflow_id=workflow_id,
              )

          return await h.result()

      @activity.defn
      async def download_frame_file(self, i: DownloadFrameFileInput) -> DownloadFrameFileOuput:
          """
          Download a frame (if not already there) and return its location.
          """
          host_hash = urlsafe_b64encode(sha256(str(self.app_config.ocsarchive_api).encode()).digest()).decode()

          cache_dir = Path(self.app_config.temporal.worker.working_dir).joinpath("cache/archive", host_hash)

          completed_dir = cache_dir.joinpath("completed")

          latest_version_dir = completed_dir.joinpath("frames", i.frame_id, "versions", "latest")

          if not i.force_download and not i.recheck_version and await aiofiles.os.path.exists(latest_version_dir):
              latest_version_dir_files = await aiofiles.os.listdir(latest_version_dir)
              if len(latest_version_dir_files) != 1:
                  raise ApplicationError("Download cache is in invalid state", non_retryable=True)

              location = latest_version_dir.joinpath(latest_version_dir_files[0])

              return DownloadFrameFileOuput(
                  file_path=str(location.resolve()),
                  cached=True
              )


          r = await self.http_client.get(
              httpx.URL(str(self.app_config.ocsarchive_api)).join(f"/frames/{i.frame_id}/"),
              follow_redirects=True
          )

          if not r.is_success and not r.is_server_error:
              raise ApplicationError("Failed to fetch frame info", r, non_retryable=True)

          try:
              r_json = r.json()
              basename: str = r_json["basename"]
              version = r_json["version_set"][0]
              version_id = str(version["id"])
              ext: str = version["extension"]
              download_url: str = version["url"]
          except Exception:
                raise ApplicationError("Failed to parse frame metadata", r, non_retryable=False)

          location = completed_dir.joinpath(
              "frames", i.frame_id, "versions", version_id, f"{basename}{ext}"
          )

          if not i.force_download and await aiofiles.os.path.exists(location):
              return DownloadFrameFileOuput(
                  file_path=str(location.resolve()),
                  cached=True
              )

          inprogress_dir = cache_dir.joinpath("inprogress")
          inprogress_location = inprogress_dir.joinpath(
              "frames", i.frame_id, "versions", version_id, f"{basename}{ext}"
            )

          await aiofiles.os.makedirs(inprogress_location.parent, exist_ok=True)

          async with aiofiles.open(inprogress_location, mode="wb") as fobj:
              async with self.http_client.stream("GET", download_url, follow_redirects=True) as resp:
                  total = int(resp.headers["content-length"])
                  async for chunk in resp.aiter_bytes():
                      await fobj.write(chunk)
                      activity.heartbeat(f"downloaded {resp.num_bytes_downloaded}/{total}")

          await aiofiles.os.makedirs(location.parent, exist_ok=True)
          await aiofiles.os.rename(inprogress_location, location)

          with suppress(Exception):
              await aiofiles.os.unlink(latest_version_dir)

          await aiofiles.os.symlink(location.parent, latest_version_dir, target_is_directory=True)

          return DownloadFrameFileOuput(
              file_path=str(location.resolve()),
              cached=False
          )

      @activity.defn
      async def delete_file(self, i: DeleteFileInput):
          await aiofiles.os.remove(i.file_path)

      @activity.defn
      async def get_hdu_dimensions(self, i: GetHduDimensionsInput) -> GetHduDimensionsOutput:
          """
          Return the dimensions of an HDU in a FITS file.
          """
          height, width = await asyncio.to_thread(
              self._get_hdu_dimensions,
              i.fits_path,
              i.hdu_index,
          )

          return GetHduDimensionsOutput(width=width, height=height)

      def _get_hdu_dimensions(self, fits_path: str, hdu_index: int) -> tuple[int, int]:
          with fits.open(fits_path) as hdus:
              hdu = self._get_hdu(hdus, hdu_index)

              shape = hdu.shape

              num_dimensions = len(shape)

              if num_dimensions != 2:
                  raise ApplicationError(
                      f"HDU has an invalid number of dimensions: {num_dimensions}",
                      non_retryable=True
                  )

          return int(shape[0]), int(shape[1])

      def _get_hdu(self, hdus, hdu_index):
          try:
              hdu = hdus[hdu_index]
          except IndexError as exc:
              raise ApplicationError("HDU index %s not found" % hdu_index, str(exc), non_retryable=True)

          return hdu

      @activity.defn
      async def create_image_file(self, i: CreateImageFileInput) -> CreateImageFileOutput:
          r = await asyncio.to_thread(self._create_image_threaded, i)
          return r

      def _create_image_threaded(self, i: CreateImageFileInput) -> CreateImageFileOutput:
          with fits.open(i.fits_path) as hdus:
              hdu = self._get_hdu(hdus, i.hdu_index)

              x, y = i.pixel_region.x, i.pixel_region.y
              w, h = i.pixel_region.w, i.pixel_region.h

              data = (ZScaleInterval()(hdu.data) * 255).astype("uint8")

              cropped = data[y:y+h, x:x+w]

              img = Image.fromarray(cropped)

              scaled = img.resize(
                  (i.pixel_size.width, i.pixel_size.height),
              )

              tmp = self.app_config.temporal.worker.working_dir.joinpath("generated")
              tmp.mkdir(exist_ok=True)

              fmt = i.fmt

              if fmt == "jpg":
                  fmt = "jpeg"

              _, file_path = tempfile.mkstemp(dir=tmp, suffix=f".{fmt}")

              scaled = scaled.convert(mode="L")

              scaled.save(file_path, format=fmt)

          with open(file_path, "rb") as fobj:
              digest = file_digest(fobj, "sha256")

          file_size = os.path.getsize(file_path)

          return CreateImageFileOutput(
              file_path=file_path,
              sha256=digest.hexdigest(),
              file_size=file_size,
          )

      @activity.defn
      def start_s3_multipart_upload(self, i: StartS3MultipartUploadInput) -> StartS3MultipartUploadOutput:
          resp = self.s3_client.create_multipart_upload(
              Bucket=self.app_config.s3.bucket,
              Key=i.object_key
          )

          upload_id = resp["UploadId"]

          return StartS3MultipartUploadOutput(
              upload_id=upload_id,
              object_key=i.object_key,
          )

      @activity.defn
      async def upload_s3_part(self, i: UploadS3PartInput) -> UploadS3PartOutput:
          # Use a presigned URL to upload using httpx, rather than the blocking method boto uses
          presigned_url = await asyncio.to_thread(
              self.s3_client.generate_presigned_url,
              "upload_part",
              Params={
                  "Bucket": self.app_config.s3.bucket,
                  "Key": i.object_key,
                  "UploadId": i.upload_id,
                  "PartNumber": i.part_number,
              }
          )

          activity.heartbeat("Generated presigned URL")


          async def gen():
              async with aiofiles.open(i.file_path, mode="rb") as fobj:
                  await fobj.seek(i.file_offset)

                  total = i.part_size
                  remaining = total

                  while remaining:
                      activity.heartbeat(f"Remaining: {remaining}")
                      chunk = await fobj.read1(remaining)

                      # EOF
                      if len(chunk) == 0:
                          break

                      remaining = total - len(chunk)

                      yield chunk

          if i.file_offset + i.part_size > i.file_size:
              content_length = i.file_size - i.file_offset
          else:
              content_length = i.part_size

          resp = await self.http_client.put(
                presigned_url,
                headers={
                    "content-length": str(content_length),
                },
                content=gen(),
                follow_redirects=True
          )

          resp.raise_for_status()

          etag = resp.headers["ETag"]

          return UploadS3PartOutput(etag=etag, part_number=i.part_number)

      @activity.defn
      def finish_s3_multipart_upload(self, i: FinishS3MultipartUploadInput) -> FinishS3MultipartUploadOutput:
          r = self.s3_client.complete_multipart_upload(
              Bucket=self.app_config.s3.bucket,
              Key=i.object_key,
              UploadId=i.upload_id,
              MultipartUpload={
                  "Parts": [
                      {
                          "ETag": x.etag,
                          "PartNumber": x.part_number,
                      }
                      for x in i.uploaded_parts
                  ]
              }
          )

          object_key = r["Key"]

          return FinishS3MultipartUploadOutput(object_key=object_key)

      @activity.defn
      def abort_s3_multipart_upload(self, i: AbortS3MultipartUploadInput):
          self.s3_client.abort_multipart_upload(
              Bucket=self.app_config.s3.bucket,
              Key=i.object_key,
              UploadId=i.upload_id,
          )

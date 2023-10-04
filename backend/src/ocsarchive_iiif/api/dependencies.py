from typing import Annotated

import boto3

from fastapi import Depends
from temporalio.client import Client
from mypy_boto3_s3.client import S3Client

from .. import config


AppConfig = Annotated[config.AppConfig, Depends(config.validate_app_config)]


async def temporal_client(config: AppConfig) -> Client:
    return await Client.connect(
        f"{config.temporal.host}:{config.temporal.port}",
        namespace=config.temporal.namespace,
    )

TemporalClient = Annotated[Client, Depends(temporal_client)]


def s3_client(app_config: AppConfig) -> S3Client:
    s3_client = boto3.client(
        "s3",
        endpoint_url=str(app_config.s3.endpoint_url),
        aws_access_key_id=app_config.s3.access_key_id,
        aws_secret_access_key=app_config.s3.secret_access_key.get_secret_value(),
        verify=app_config.s3.verify_tls,
    )

    return s3_client

S3Client = Annotated[S3Client, Depends(s3_client)]

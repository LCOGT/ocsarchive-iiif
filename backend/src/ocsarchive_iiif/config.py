from __future__ import annotations

from typing import Tuple, Type, Annotated, Literal
from functools import cache

from pydantic import Field, BaseModel, DirectoryPath, FilePath, AnyHttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource


class BaseConfig(BaseSettings):

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        # ignore dotenv & files secret
        return init_settings, env_settings


class FastAPI(BaseModel):
    debug: Annotated[bool, Field(description="Run FastAPI in debug mode")] = False


class Temporal(BaseModel):
    host: Annotated[str, Field(description="Temporal Server host name")] = "localhost"

    port: Annotated[int, Field(description="Temporal Server gRPC port")] = 7233

    namespace: Annotated[str, Field(description="Temporal namespace")] = "default"

    worker: TemporalWorker = Field(default_factory=lambda: TemporalWorker())


class TemporalWorker(BaseModel):
    log_level: Literal["critical", "error", "warn", "info", "debug"] = "warn"

    reload: TemporalWorkerReload = Field(default_factory=lambda: TemporalWorkerReload())

    working_dir: Annotated[DirectoryPath, Field(description="Scratch space for the worker")] = DirectoryPath("/tmp")


class TemporalWorkerReload(BaseModel):
    enabled: Annotated[bool, Field(description="Whether to reload/restart the worker on any changes to path")] = False

    path: Annotated[FilePath | DirectoryPath, Field(description="Path to watch for changes")] = DirectoryPath(".")


class S3(BaseModel):
    endpoint_url: Annotated[AnyHttpUrl, Field(description="S3 compatible API URL")]

    access_key_id: Annotated[str, Field(description="Access Key ID")]

    secret_access_key: Annotated[SecretStr, Field(description="Secret Access Key")]

    verify_tls: Annotated[bool, Field(description="Verify TLS cert is valid")] = True

    bucket: Annotated[str, Field(description="S3 Bucket")] = "ocsarchive-iiif"


class AppConfig(BaseConfig):
    model_config = SettingsConfigDict(
        env_prefix="OCSARCHIVE_IIIF_BACKEND_",
        env_nested_delimiter="__",
    )

    fastapi: FastAPI = Field(default_factory=lambda: FastAPI())

    temporal: Temporal = Field(default_factory=lambda: Temporal())

    ocsarchive_api: Annotated[AnyHttpUrl, Field(description="Base URL to an OCS Archive API")]

    s3: S3 = Field(default_factory=lambda: S3.model_validate({}))

@cache
def validate_app_config() -> AppConfig:
    return AppConfig.model_validate({})

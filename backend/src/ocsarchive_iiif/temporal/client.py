from temporalio.client import Client

from ..config import validate_app_config


def connect_client():
    config = validate_app_config()

    return Client.connect(
        f"{config.temporal.host}:{config.temporal.port}",
        namespace=config.temporal.namespace,
    )

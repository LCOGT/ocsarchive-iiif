from __future__ import annotations

from textwrap import dedent

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import validate_app_config
from . import routes, zpages, dragon


def app_factory():
    app_config = validate_app_config()

    app = FastAPI(
      title="ocsarchive-iiif",
      description=dedent("""
        [IIIF Image API](https://iiif.io/api/image/3.0/) for the
        [OCS Science Archive](https://github.com/observatorycontrolsystem/science-archive)

        Primary use case for this service is to generate image tiles
        just-in-time (and efficiently) for "deep zoom" viewers like
        [OpenSeadragon](http://openseadragon.github.io/examples/tilesource-iiif/).

        <a href="/swagger" target="_self">Swagger</a> | <a href="/" target="_self">Redoc</a>
      """
      ),
      version="1.0.0",
      debug=app_config.fastapi.debug,
      docs_url="/swagger",
      redoc_url="/",
      separate_input_output_schemas=False,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
    )

    app.include_router(routes.router)
    app.include_router(dragon.router)
    app.include_router(zpages.router)

    return app

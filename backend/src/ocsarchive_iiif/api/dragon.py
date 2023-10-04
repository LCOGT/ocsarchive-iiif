from textwrap import dedent

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse


from .path_params import (
    FrameIdPathParam,
    HduIndexPathParam,
)

router = APIRouter(tags=["Example OpenSeadragon Viewer"])


@router.get("/examples/dragon/view/{frame_id}/fits/hdus/{hdu_index}", response_class=HTMLResponse)
async def view_frame(
    frame_id: FrameIdPathParam,
    hdu_index: HduIndexPathParam,
    req: Request,
):
    """
    Simple OpenSeadragon viewer.
    """
    return dedent(f"""
    <html>
      <head>
        <title>{frame_id}/fits/huds/{hdu_index}</title>
      </head>
      <body>
      <div id="viewer" style="width: 800px; height: 600px; margin: auto;"></div>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/openseadragon/4.1.0/openseadragon.min.js"></script>
      <script type="text/javascript">
        const viewer = OpenSeadragon({{
          id: "viewer",
          prefixUrl: "https://cdnjs.cloudflare.com/ajax/libs/openseadragon/4.1.0/images/",
          tileSources: ["{req.url_for("get_image_information", frame_id=frame_id, hdu_index=hdu_index)}"]
        }});
      </script>
      </body>
    </html>
    """)

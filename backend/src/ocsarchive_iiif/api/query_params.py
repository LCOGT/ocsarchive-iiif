from typing import Annotated

from fastapi import Query


ReuseWorkflowQueryParam = Annotated[
    bool,
    Query(description="reuse previous workflow result (takes precedence)")
]


ForceDownloadQueryParam = Annotated[
    bool,
    Query(description="download the frame file even if it's cached")
]


RecheckVersionQueryParam = Annotated[
    bool,
    Query(description="check if there's a new version of the frame file")
]

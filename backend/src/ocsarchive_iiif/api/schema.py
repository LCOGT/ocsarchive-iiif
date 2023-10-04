from __future__ import annotations

from typing import Annotated, Literal, Optional, NamedTuple, Any, TypeAlias, Union, Self
from enum import StrEnum
from textwrap import dedent

from pydantic import (
    conint,
    Field,
    BaseModel as PydanticBaseModel,
    ConfigDict,
    GetJsonSchemaHandler,
    model_serializer,
    model_validator,
    RootModel
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema


def snake_to_lower_camel(s: str) -> str:
    words = s.split("_")

    return "".join([words[0].lower()] + [w.capitalize() for w in words[1:]])


class BaseModel(PydanticBaseModel):
    """
    BaseModel with some sane defaults
    """
    model_config = ConfigDict(alias_generator=snake_to_lower_camel, populate_by_name=True)


class RealStrEnum(StrEnum):
    """
    pydantic renders the JSON schema for Enums w/ one value as `const`.
    Use this instread to have consistent behavior.
    """
    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: CoreSchema,
        handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema = handler(core_schema)
        json_schema = handler.resolve_ref_schema(json_schema)
        json_schema.pop("const", None)

        json_schema["enum"] = [x.name for x in cls]

        return json_schema


class ImageInfoSize(BaseModel):
    type_: Annotated[
        Optional[Literal["Size"]],
        Field(alias="type", description="The type of the object.")
    ] = None


    width: Annotated[
        int,
        conint(strict=True, ge=1),
        Field(ge=1, description="The width in pixels of the image to be requested, given as an integer.")
    ]

    height: Annotated[
        int,
        conint(strict=True, ge=1),
        Field(ge=1, description="The height in pixels of the image to be requested, given as an integer.")
    ]


class ImageQuality(RealStrEnum):
    default = "default"


class ImageFormat(RealStrEnum):
    webp = "webp"
    png = "png"
    jpg = "jpg"


class ImageInfoTile(BaseModel):
    type_: Annotated[
        Optional[Literal["Tile"]],
        Field(alias="type", description="The type of the object.")
    ] = None


    scale_factors: Annotated[
        list[Annotated[int, conint(ge=1), Field(ge=1)]],
        Field(
            description=dedent(r"""
            The set of resolution scaling factors for the image’s predefined tiles, expressed as positive
            integers by which to divide the full size of the image.\
            For example, a scale factor of 4 indicates that the service can efficiently deliver images at
            1/4 or 25% of the height and width of the full image.
            """
            )
        )
    ]

    width: Annotated[
        int,
        conint(ge=1),
        Field(ge=1, description=dedent(r"""
            The width in pixels of the predefined tiles to be requested, given as an integer.
            """
            )
        )
    ]

    height: Annotated[
        Annotated[int, conint(ge=1), Field(ge=1)] | None,
        Field(
            description=dedent(r"""
            The height in pixels of the predefined tiles to be requested, given as an integer.\
            If it is not specified, then it defaults to the same as width, resulting in square tiles.
            """
            )
        )
    ] = None


class ImageInfoResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    context: Annotated[
        Literal["http://iiif.io/api/image/3/context.json"],
        Field(alias="@context")
    ] = "http://iiif.io/api/image/3/context.json"

    id_: Annotated[
        str,
        Field(
            alias="id",
            description=dedent(r"""
            The base URI of the image as defined in URI Syntax, including scheme, server, prefix and
            identifier without a trailing slash.
            """
            )
        ),
    ]

    type_: Annotated[
        Literal["ImageService3"],
        Field(
            alias="type",
            description="The type for the Image API.",
        )
    ] = "ImageService3"

    protocol: Annotated[
        Literal["http://iiif.io/api/image"],
        Field(
            description=dedent(r"""
            Can be used to determine that the document describes an image service which is a version of the
            IIIF Image API.
            """
            )
        )
    ] =  "http://iiif.io/api/image"

    profile: Annotated[
        Literal["level1"],
        Field(description="https://iiif.io/api/image/3.0/compliance/")
    ] = "level1"

    width: Annotated[
        int,
        conint(strict=True, ge=1),
        Field(
            ge=1,
            description="The width in pixels of the full image, given as an integer.",
        )
    ]

    height: Annotated[
        int,
        conint(strict=True, ge=1),
        Field(
            ge=1,
            description="The height in pixels of the full image, given as an integer.",
        )
    ]

    max_width: Annotated[
        Annotated[int, conint(strict=True, ge=1), Field(ge=1)] | Annotated[None, Field(title="No Limit")],
        Field(
            description=dedent(r"""
            The maximum width in pixels supported for this image.\
            Clients must not expect requests with a width greater than this value to be supported.\
            maxWidth must be specified if maxHeight is specified.
            """
            )
        )
    ] = None

    max_height: Annotated[
        Annotated[int, conint(strict=True, ge=1), Field(ge=1)] | Annotated[None, Field(title="No Limit")],
        Field(
            description=dedent(r"""
            The maximum height in pixels supported for this image.\
            Clients must not expect requests with a height greater than this value to be supported.\
            If maxWidth is specified and maxHeight is not, then clients should infer that maxHeight = maxWidth.
            """
            )
        )
    ] = None

    max_area: Annotated[
        Annotated[int, conint(strict=True, ge=1), Field(ge=1)] | Annotated[None, Field(title="No Limit")],
        Field(
            description=dedent(r"""
            The maximum area in pixels supported for this image. Clients must not expect requests with a
            width*height greater than this value to be supported.
            """
            )
        )
    ] = None


    sizes: Annotated[
        list[ImageInfoSize] | Annotated[None, Field(title="None", description="No preferences")],
        Field(description="Preferred height and width combinations for representations of the full image.")
    ] = None

    tiles: Annotated[
        list[ImageInfoTile] | Annotated[None, Field(title="None", description="No preferences")],
        Field(
            description=dedent(r"""
            Set of image regions that have a consistent height and width, over a series of resolutions,
            that can be stitched together visually.
            """
            )
        )
    ] = None

    preferred_formats: Annotated[
        list[ImageFormat] | Annotated[None, Field(title="None", description="No preferences")],
        Field(
            description=dedent(r"""
            An array of strings that are the preferred format parameter values, arranged in order of preference.
            """
            )
        )
    ] = [ImageFormat.webp, ImageFormat.png, ImageFormat.jpg]

    rights: Annotated[
        str | None,
        Field(
            description=dedent(r"""
            A string that identifies a license or rights statement that applies to the content of this image.
            """
            )
        )
    ] = None

    extra_qualities: Annotated[
        list[str] | None,
        Field(
            description="An array of strings that can be used as the quality parameter, in addition to `default`."
        )
    ] = None

    extra_formats: Annotated[
        list[str] | None,
        Field(
            description=dedent(r"""
            An array of strings that can be used as the format parameter, in addition to the ones specified
            in the referenced profile.
            """
            )
        )
    ] = [ImageFormat.webp]

    extra_features: Annotated[
        list[str] | None,
        Field(
            description=dedent(r"""
            An array of strings identifying features supported by the service, in addition to the ones
            specified in the referenced profile.
            """
            )
        )
    ] = None



class LiteralRegionMixin(BaseModel):
    kind: str
    value: str

    @model_serializer(mode="wrap", when_used="json")
    def _to_string(self, handler, info) -> str:
        handler(self)

        return f"{self.kind.lower()}"

    @model_validator(mode="wrap")
    @classmethod
    def _validate(cls, v, handler, info) -> Any:
        if isinstance(v, cls):
            return v

        if isinstance(v, str):
            return handler(dict(value=v))

        return handler(v)

class FullRegion(LiteralRegionMixin):
    kind: Literal["FullRegion"] = "FullRegion"
    value: Literal["full"] = "full"

class SquareRegion(LiteralRegionMixin):
    kind: Literal["SquareRegion"] = "SquareRegion"
    value: Literal["square"] = "square"

class PixelRegion(BaseModel):
    kind: Literal["PixelRegion"] = "PixelRegion"

    x: Annotated[int, Field(ge=0)]
    y: Annotated[int, Field(ge=0)]
    w: Annotated[int, Field(ge=1)]
    h: Annotated[int, Field(ge=1)]

    @model_serializer(mode="wrap", when_used="json")
    def _to_string(self, handler, info) -> str:
        handler(self)

        return str(self)

    @model_validator(mode="wrap")
    @classmethod
    def _validate(cls, v, handler, info) -> Any:
        if isinstance(v, cls):
            return v

        if isinstance(v, str):
            x, y, w, h = v.split(",")
            return handler(dict(x=x, y=y, w=w, h=h))

        return handler(v)

    def __str__(self):
        return f"{self.x},{self.y},{self.w},{self.h}"


class PercentRegion(BaseModel):
    kind: Literal["PercentRegion"] = "PercentRegion"

    x: Annotated[float, Field(ge=0)]
    y: Annotated[float, Field(ge=0)]
    w: Annotated[float, Field(gt=0)]
    h: Annotated[float, Field(gt=0)]

    @model_serializer(mode="wrap", when_used="json")
    def _to_string(self, handler, info) -> str:
        handler(self)

        return f"pct:{self.x},{self.y},{self.w},{self.h}"

    @model_validator(mode="wrap")
    @classmethod
    def _validate(cls, v, handler, info) -> Self:
        if isinstance(v, cls):
            return v

        if isinstance(v, str):
            assert v.startswith("pct:")
            x, y, w, h = v.removeprefix("pct:").split(",")
            return handler(dict(x=x, y=y, w=w, h=h))

        return handler(v)


Region = Union[FullRegion, SquareRegion, PercentRegion, PixelRegion]


class MaxSize(BaseModel):
    kind: Literal["MaxSize"] = "MaxSize"
    upscaleable: bool

    @model_validator(mode="wrap")
    @classmethod
    def _validate(cls, v, handler, info) -> Self:
        if isinstance(v, cls):
            return v

        if isinstance(v, str):
            upscale = v.startswith("^")
            assert v.removeprefix("^") == "max"
            return handler(dict(upscaleable=upscale))

        return handler(v)


class FixedWidthSize(BaseModel):
    kind: Literal["FixedWidthSize"] = "FixedWidthSize"
    upscaleable: bool
    width: Annotated[int, Field(ge=1)]

    @model_validator(mode="wrap")
    @classmethod
    def _validate(cls, v, handler, info) -> Self:
        if isinstance(v, cls):
            return v

        if isinstance(v, str):
            upscale = v.startswith("^")
            elms = v.removeprefix("^").split(",")
            assert len(elms) == 2 and elms[1] == "", f"{v} not in `w,` format"
            return handler(dict(upscaleable=upscale, width=elms[0]))

        return handler(v)

class FixedHeightSize(BaseModel):
    kind: Literal["FixedHeightSize"] = "FixedHeightSize"
    upscaleable: bool
    height: Annotated[int, Field(ge=1)]

    @model_validator(mode="wrap")
    @classmethod
    def _validate(cls, v, handler, info) -> Self:
        if isinstance(v, cls):
            return v

        if isinstance(v, str):
            upscale = v.startswith("^")
            elms = v.removeprefix("^").split(",")
            assert len(elms) == 2 and elms[0] == "", f"{v} not in `,h` format"
            return handler(dict(upscaleable=upscale, height=elms[1]))

        return handler(v)

class PercentSize(BaseModel):
    kind: Literal["PercentSize"] = "PercentSize"
    upscaleable: bool
    percent: Annotated[float, Field(gt=0, le=100)]

    @model_validator(mode="wrap")
    @classmethod
    def _validate(cls, v, handler, info) -> Self:
        if isinstance(v, cls):
            return v

        if isinstance(v, str):
            upscale = v.startswith("^")
            assert v.removeprefix("^").startswith("pct:"), f"{v} not in `pct:n` format"

            percent = v.removeprefix("^").removeprefix("pct:")

            return handler(dict(upscaleable=upscale, percent=percent))

        return handler(v)

class PixelSize(BaseModel):
    kind: Literal["PixelSize"] = "PixelSize"
    upscaleable: bool
    width: Annotated[int, Field(ge=1)]
    height: Annotated[int, Field(ge=1)]

    @model_validator(mode="wrap")
    @classmethod
    def _validate(cls, v, handler, info) -> Self:
        if isinstance(v, cls):
            return v

        if isinstance(v, str):
            upscale = v.startswith("^")

            elms = v.removeprefix("^").split(",")
            assert len(elms) == 2, f"{v} not in `w,h` format"
            width, height = elms

            return handler(dict(upscaleable=upscale, width=width, height=height))

        return handler(v)

    def __str__(self):
        up = "^" if self.upscaleable else ""
        return f"{up}{self.width},{self.height}"

class PreservedAspectPixelSize(BaseModel):
    kind: Literal["PreservedAspectPixelSize"] = "PreservedAspectPixelSize"
    upscaleable: bool
    width: Annotated[int, Field(ge=1)]
    height: Annotated[int, Field(ge=1)]

    @model_validator(mode="wrap")
    @classmethod
    def _validate(cls, v, handler, info) -> Self:
        if isinstance(v, cls):
            return v

        if isinstance(v, str):
            upscale = v.startswith("^")

            assert v.removeprefix("^").startswith("!"), f"{v} does not start with `!`"

            elms = v.removeprefix("^").removeprefix("!").split(",")
            assert len(elms) == 2, f"{v} not in `w,h` format"
            width, height = elms

            return handler(dict(upscaleable=upscale, width=width, height=height))

        return handler(v)


Size = Union[MaxSize, FixedWidthSize, FixedHeightSize, PercentSize, PixelSize, PreservedAspectPixelSize]

class ImageOperationSpec(BaseModel):

    region: Region

    size: Size

from __future__ import annotations

from typing import Annotated, Literal, Union

from textwrap import dedent

from fastapi import Path
from pydantic import AfterValidator, Field, TypeAdapter

from . import schema


FrameIdPathParam = Annotated[
    str,
    Path(
        alias="frame_id",
        description="Archive API frame ID",
    )
]

HduIndexPathParam = Annotated[
    int,
    Path(
        alias="hdu_index",
        description="FITS HDU index to use", ge=0
    )
]


FullRegion = Annotated[
    Literal["full"],
    Field(description="The full image is returned, without any cropping."),
]

SquareRegion = Annotated[
    Literal["square"],
    Field(
        description=dedent(r"""
        The region is defined as an area where the width and height are both equal to the length of the
        shorter dimension of the full image. The region may be positioned anywhere in the longer dimension
        of the full image at the server’s discretion, and centered is often a reasonable default.
        """
        )
    )
]

PixelRegion = Annotated[
    str,
    Field(
        title="Pixel",
        pattern=r"^[0-9]+,[0-9]+,[0-9]+,[0-9]+$",
        examples=["x,y,w,h"],
        description=dedent(r"""
        The region of the full image to be returned is specified in terms of absolute pixel values.
        The value of x represents the number of pixels from the 0 position on the horizontal axis.
        The value of y represents the number of pixels from the 0 position on the vertical axis.
        Thus the x,y position 0,0 is the upper left-most pixel of the image.
        w represents the width of the region and h represents the height of the region in pixels.
        """
        ),
    ),
    AfterValidator(lambda v: schema.PixelRegion.model_validate(v) and v)
]

PercentRegion = Annotated[
    str,
    Field(
        title="Percent",
        pattern=r"^pct:([0-9]*[.])?[0-9]+,([0-9]*[.])?[0-9]+,([0-9]*[.])?[0-9]+,([0-9]*[.])?[0-9]+$",
        examples=["pct:x,y,w,h"],
        description=dedent(r"""
        The region to be returned is specified as a sequence of percentages of the full image’s dimensions,
        as reported in the image information document. Thus, x represents the number of pixels from the
        0 position on the horizontal axis, calculated as a percentage of the reported width. w represents
        the width of the region, also calculated as a percentage of the reported width. The same applies
        to y and h respectively.
        """
        ),
    ),
    AfterValidator(lambda v: schema.PercentRegion.model_validate(v) and v)
]


RegionPathParam = Annotated[
    Union[
        FullRegion,
        SquareRegion,
        PixelRegion,
        PercentRegion,
    ],
    Path(
        alias="region",
        description=dedent(r"""
        <https://iiif.io/api/image/3.0/#41-region>

        The region parameter defines the rectangular portion of the underlying image content to be returned.
        Region can be specified by pixel coordinates, percentage or by the value `full`, which specifies
        that the full image should be returned.
        """
        ),
        examples=["full", "square", "x,y,w,h", "pct:x,y,w,h"],
    ),
]

MaxSize = Annotated[
    Literal["max"],
    Field(
        title="Maximum",
        description=dedent(r"""
        The extracted region is returned at the maximum size available, but will not be upscaled.
        The resulting image will have the pixel dimensions of the extracted region, unless it is
        constrained to a smaller size by `maxWidth`, `maxHeight`, or `maxArea` as defined in the
        [Technical Properties](https://iiif.io/api/image/3.0/#52-technical-properties) section.
        """
        )
    )
]

UpscaleableMaxSize = Annotated[
    Literal["^max"],
    Field(
        title="Upscaleable Maximum",
        description=dedent(r"""
        The extracted region is scaled to the maximum size permitted by `maxWidth`, `maxHeight`, or
        `maxArea` as defined in the Technical Properties section. If the resulting dimensions are
        greater than the pixel width and height of the extracted region, the extracted region is
        upscaled.
        """
        )
    )
]

FixedWidthSize = Annotated[
    str,
    Field(
        title="Fixed Width",
        pattern=r"^[0-9]+,$",
        description=dedent(r"""
        The extracted region should be scaled so that the width of the returned image is exactly equal to `w`.
        The value of `w` **must not** be greater than the width of the extracted region.
        """
        ),
    )
]

UpscaleableFixedWidthSize = Annotated[
    str,
    Field(
        title="Upscaleable Fixed Width",
        pattern=r"^\^[0-9]+,$",
        description=dedent(r"""
        The extracted region should be scaled so that the width of the returned image is exactly equal to `w`.
        If `w` is greater than the pixel width of the extracted region, the extracted region is upscaled.
        """
        ),
    )
]

FixedHeightSize = Annotated[
    str,
    Field(
        title="Fixed Height",
        pattern=r"^,[0-9]+$",
        description=dedent(r"""
        The extracted region should be scaled so that the height of the returned image is exactly equal to `h`.
        The value of `h` **must not** be greater than the height of the extracted region.
        """
        ),
    )
]

UpscaleableFixedHeightSize = Annotated[
    str,
    Field(
        title="Upscaleable Fixed Height",
        pattern=r"^\^,[0-9]+$",
        description=dedent(r"""
        The extracted region should be scaled so that the height of the returned image is exactly equal to `h`.
        If `h` is greater than the pixel height of the extracted region, the extracted region is upscaled.
        """
        ),
    )
]

PercentSize = Annotated[
    str,
    Field(
        title="Percent",
        pattern=r"pct:([0-9]*[.])?[0-9]+$",
        description=dedent(r"""
        The width and height of the returned image is scaled to `n` percent of the width and height of the
        extracted region.
        The value of `n` **must not** be greater than 100.
        """
        ),
    )
]

UpscaleablePercentSize = Annotated[
    str,
    Field(
        title="Upscaleable Percent",
        pattern=r"\^pct:([0-9]*[.])?[0-9]+$",
        description=dedent(r"""
        The width and height of the returned image is scaled to `n` percent of the width and height of the
        extracted region.
        For values of `n` greater than 100, the extracted region is upscaled.
        """
        ),
    )
]

PixelSize = Annotated[
    str,
    Field(
        title="Pixel",
        pattern=r"^[0-9]+,[0-9]+$",
        description=dedent(r"""
        The width and height of the returned image are exactly `w` and `h`.
        The aspect ratio of the returned image **may** be significantly different than the extracted region,
        resulting in a distorted image.
        The values of `w` and `h` **must not** be greater than the corresponding pixel dimensions of the
        extracted region.
        """
        ),
    )
]

UpscaleablePixelSize = Annotated[
    str,
    Field(
        title="Upscaleable Pixel",
        pattern=r"^\^[0-9]+,[0-9]+$",
        description=dedent(r"""
        The width and height of the returned image are exactly `w` and `h`.
        The aspect ratio of the returned image **may** be significantly different than the extracted region,
        resulting in a distorted image.
        If `w` and/or `h` are greater than the corresponding pixel dimensions of the extracted region, the
        extracted region is upscaled.
        """
        ),
    )
]

PreservedAspectPixelSize = Annotated[
    str,
    Field(
        title="Preserved Aspect Ratio Pixel",
        pattern=r"^[!][0-9]+,[0-9]+$",
        description=dedent(r"""
        The extracted region is scaled so that the width and height of the returned image are
        *not greater* than `w` and `h`, while maintaining the aspect ratio.
        The returned image must be as large as possible but not larger than the extracted region,
        `w` or `h`, or server-imposed limits.
        """
        ),
    )
]

UpscaleablePreservedAspectPixelSize = Annotated[
    str,
    Field(
        title="Upscaleable Preserved Aspect Ratio Pixel",
        pattern=r"^\^[!][0-9]+,[0-9]+$",
        description=dedent(r"""
        The extracted region is scaled so that the width and height of the returned image are
        *not greater* than `w` and `h`, while maintaining the aspect ratio. The returned image must
        be as large as possible but not larger than `w`, `h`, or server-imposed limits.
        """
        ),
    )
]

SizePathParam = Annotated[
    Union[
        MaxSize,
        UpscaleableMaxSize,
        FixedWidthSize,
        UpscaleableFixedWidthSize,
        FixedHeightSize,
        UpscaleableFixedHeightSize,
        PercentSize,
        UpscaleablePercentSize,
        PixelSize,
        UpscaleablePixelSize,
        PreservedAspectPixelSize,
        UpscaleablePreservedAspectPixelSize,
    ],
    Path(
        alias="size",
        description=dedent(r"""
        <https://iiif.io/api/image/3.0/#42-size>

        The size parameter specifies the dimensions to which the extracted region, which might be the full
        image, is to be scaled.\
        With the exception of the `w,h` and `^w,h` forms, the returned image maintains the aspect ratio of
        the extracted region as closely as possible.\
        Sizes prefixed with `^` allow upscaling of the extracted region when its pixel dimensions are less
        than the pixel dimensions of the scaled region.
        """
        ),
        examples=[
            "w,h", "^w,h", "max", "^max", "w,", "^w,", ",h", "^,h",
            "pct:n", "^pct:n", "!w,h", "^!w,h",
        ],

    ),
    AfterValidator(lambda x: TypeAdapter(schema.Size).validate_python(x) and x),
]

RotationPathParam = Annotated[
    Literal["0"],
    Path(
        alias="rotation",
        description=dedent(r"""
        <https://iiif.io/api/image/3.0/#43-rotation>

        The rotation parameter specifies mirroring and rotation.
        \
        We do not support this feature, so only `0` is allowed.
        """
        ),
        examples=["0"],
    )
]

QualityPathParam = Annotated[
    schema.ImageQuality,
    Path(
        alias="quality",
        description=dedent(r"""
        <https://iiif.io/api/image/3.0/#quality>

        The quality parameter determines whether the image is delivered in default, color, grayscale, etc.
        quality.
        \
        We only support `default`.
        """
        ),
    ),
]

FormatPathParam = Annotated[
    schema.ImageFormat,
    Path(
        alias="format",
        description=dedent(r"""
        <https://iiif.io/api/image/3.0/#45-format>

        The format of the returned image is expressed as a suffix, mirroring common filename extensions,
        at the end of the URI.
        """
        )
    )
]

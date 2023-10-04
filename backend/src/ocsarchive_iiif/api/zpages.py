from __future__ import annotations

from typing import Literal

from fastapi import APIRouter

from .dependencies import AppConfig


router = APIRouter(tags=["zpages"])


@router.get("/configz", tags=["zpages"], include_in_schema=False)
async def get_config(c: AppConfig) -> AppConfig:
    return c


@router.get("/statuz", tags=["zpages"], include_in_schema=False)
async def get_status() -> Literal["Ok"]:
    return "Ok"

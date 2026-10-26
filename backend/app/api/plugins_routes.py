"""
API routes for saving, listing, and loading plugins .
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.storage import get_plugin, list_plugins, save_plugin
from app.runtime.packaging import MAX_CODE_LENGTH

router = APIRouter()


class SavePluginRequest(BaseModel):
    name: str = Field(..., description="Plugin name")
    code: str = Field(..., description="Python source code")


class SavePluginResponse(BaseModel):
    id: int
    name: str


class PluginSummaryResponse(BaseModel):
    id: int
    name: str


class PluginDetailResponse(BaseModel):
    id: int
    name: str
    code: str


@router.post("/plugins", response_model=SavePluginResponse, status_code=status.HTTP_200_OK)
def create_plugin(payload: SavePluginRequest) -> SavePluginResponse:
    """Save a plugin to SQLite database with validation."""
    name = payload.name.strip()
    if not name or len(name) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plugin name must be between 1 and 100 characters",
        )

    code = payload.code
    if not code.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No code provided",
        )

    if len(code) > MAX_CODE_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Code exceeds maximum allowed size of {MAX_CODE_LENGTH} characters",
        )

    result = save_plugin(name, code)
    return SavePluginResponse(id=result["id"], name=result["name"])


@router.get("/plugins", response_model=list[PluginSummaryResponse])
def get_all_plugins() -> list[PluginSummaryResponse]:
    """List all saved plugins (id and name)."""
    plugins = list_plugins()
    return [PluginSummaryResponse(id=p["id"], name=p["name"]) for p in plugins]


@router.get("/plugins/{plugin_id}", response_model=PluginDetailResponse)
def get_single_plugin(plugin_id: int) -> PluginDetailResponse:
    """Load one saved plugin by id."""
    plugin = get_plugin(plugin_id)
    if plugin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plugin not found",
        )
    return PluginDetailResponse(
        id=plugin["id"],
        name=plugin["name"],
        code=plugin["code"],
    )

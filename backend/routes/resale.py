from __future__ import annotations

from functools import lru_cache
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from resale.models import Item, ItemStatus, Priority
from resale.queue import build_daily_queue
from resale.store import InventoryStore


router = APIRouter(prefix="/api/resale", tags=["resale"])


@lru_cache(maxsize=1)
def get_store() -> InventoryStore:
    return InventoryStore()


class ItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    category: str = "other"
    priority: Priority = Priority.MEDIUM
    condition: str = "unknown"
    identifiers: dict[str, str] = Field(default_factory=dict)
    source_refs: list[str] = Field(default_factory=list)
    photo_refs: list[str] = Field(default_factory=list)
    research_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    price_low: float = Field(default=0.0, ge=0.0)
    price_high: float = Field(default=0.0, ge=0.0)
    target_price: float = Field(default=0.0, ge=0.0)
    expected_effort_minutes: int = Field(default=15, ge=1, le=1440)
    platform: str | None = None
    next_action: str | None = None
    notes: str = ""
    acquired_at: str | None = None


class StatusTransition(BaseModel):
    status: ItemStatus
    platform: str | None = None
    note: str | None = None


class JsonImport(BaseModel):
    payload: str
    preview: bool = True


@router.get("/items")
def list_items(status: list[ItemStatus] | None = Query(default=None)) -> dict[str, Any]:
    items = get_store().list_items(statuses=status)
    return {"items": [item.to_dict() for item in items], "count": len(items)}


@router.post("/items", status_code=201)
def create_item(request: ItemCreate) -> dict[str, Any]:
    payload = request.model_dump() if hasattr(request, "model_dump") else request.dict()
    item = get_store().save(Item(**payload), event_type="item.captured")
    return {"item": item.to_dict(), "external_action": False}


@router.get("/items/{item_id}")
def get_item(item_id: str) -> dict[str, Any]:
    item = get_store().get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="resale item not found")
    return {"item": item.to_dict()}


@router.post("/items/{item_id}/status")
def transition_item(item_id: str, request: StatusTransition) -> dict[str, Any]:
    try:
        item = get_store().transition(
            item_id,
            request.status,
            platform=request.platform,
            note=request.note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"item": item.to_dict(), "external_action": False}


@router.delete("/items/{item_id}")
def delete_item(item_id: str) -> dict[str, bool]:
    deleted = get_store().delete(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="resale item not found")
    return {"deleted": True}


@router.get("/queue")
def daily_queue(limit: int = Query(default=20, ge=1, le=200)) -> dict[str, Any]:
    entries = build_daily_queue(get_store().list_items(), limit=limit)
    return {
        "queue": [
            {
                "item_id": entry.item_id,
                "title": entry.title,
                "status": entry.status,
                "priority": entry.priority,
                "action": entry.action,
                "expected_value": entry.expected_value,
                "expected_effort_minutes": entry.expected_effort_minutes,
                "score": entry.score,
            }
            for entry in entries
        ],
        "count": len(entries),
        "external_action": False,
    }


@router.get("/summary")
def summary() -> dict[str, Any]:
    return get_store().summary()


@router.get("/export/json", response_class=PlainTextResponse)
def export_json() -> str:
    return get_store().export_json()


@router.get("/export/csv", response_class=PlainTextResponse)
def export_csv() -> str:
    return get_store().export_csv()


@router.post("/import/json")
def import_json(request: JsonImport) -> dict[str, Any]:
    try:
        items = get_store().import_json(request.payload, preview=request.preview)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "items": [item.to_dict() for item in items],
        "count": len(items),
        "preview": request.preview,
        "external_action": False,
    }

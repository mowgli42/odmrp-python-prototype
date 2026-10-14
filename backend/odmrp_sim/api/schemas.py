"""Pydantic request/response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NodeSpec(BaseModel):
    id: int | None = None
    x: float
    y: float
    range: float | None = None


class NetworkCreate(BaseModel):
    nodes: list[NodeSpec]
    range: float = 130.0
    params: dict[str, Any] | None = None
    seed: int = 42


class PositionUpdate(BaseModel):
    x: float
    y: float


class GroupJoin(BaseModel):
    group: str


class MessageSend(BaseModel):
    source: int
    group: str
    text: str


class StepBody(BaseModel):
    dt: float = Field(gt=0)


class SpeedBody(BaseModel):
    multiplier: float = Field(gt=0, le=100)


class ParamsBody(BaseModel):
    params: dict[str, Any]

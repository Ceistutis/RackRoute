"""Load JSON layouts without exposing serialization concerns to the domain."""

import json
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from datacenter.models import DataCenterLayout, Position, Rack


class LayoutLoadError(ValueError):
    """A layout file cannot be read, parsed, or converted into a valid layout."""


class _RackData(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    x: StrictInt
    y: StrictInt


class _LayoutData(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    width: Annotated[StrictInt, Field(gt=0)]
    height: Annotated[StrictInt, Field(gt=0)]
    cell_size_meters: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    racks: list[_RackData]
    blocked_cells: list[Annotated[list[StrictInt], Field(min_length=2, max_length=2)]]


def load_layout(path: str | Path) -> DataCenterLayout:
    """Read a UTF-8 JSON file and return a validated domain layout.

    All five top-level fields are required; empty rack/block lists are allowed.
    Unknown fields and type coercion are rejected. Domain models enforce rack
    identity and occupancy rules. Errors include the source path and cause.
    """
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
        data = _LayoutData.model_validate(raw)
        return DataCenterLayout(
            width=data.width,
            height=data.height,
            cell_size_meters=data.cell_size_meters,
            racks=tuple(Rack(rack.id, Position(rack.x, rack.y)) for rack in data.racks),
            blocked_positions=frozenset(Position(x, y) for x, y in data.blocked_cells),
        )
    except (OSError, ValueError, OverflowError) as error:
        raise LayoutLoadError(f"Cannot load layout from {source}: {error}") from error

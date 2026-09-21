"""JSON boundary validation and conversion to domain objects."""

import json
from pathlib import Path

import pytest

from datacenter.infrastructure import LayoutLoadError, load_layout
from datacenter.models import DataCenterLayout, Position, Rack
from datacenter.services import CableRouteService


@pytest.fixture
def payload() -> dict:
    return {
        "width": 3,
        "height": 3,
        "cell_size_meters": 0.5,
        "racks": [{"id": "A", "x": 0, "y": 0}, {"id": "B", "x": 2, "y": 0}],
        "blocked_cells": [[1, 0]],
    }


def write_layout(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "layout.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_converts_json_to_domain_objects(tmp_path: Path, payload: dict) -> None:
    layout = load_layout(str(write_layout(tmp_path, payload)))
    assert isinstance(layout, DataCenterLayout)
    assert (layout.width, layout.height, layout.cell_size_meters) == (3, 3, 0.5)
    assert layout.racks == (Rack("A", Position(0, 0)), Rack("B", Position(2, 0)))
    assert layout.blocked_positions == frozenset({Position(1, 0)})
    route = CableRouteService(layout).calculate_route("A", "B")
    assert route.steps == 4
    assert route.distance_meters == 2


def test_repository_example_is_routable() -> None:
    path = Path(__file__).resolve().parents[2] / "data" / "example_datacenter.json"
    layout = load_layout(path)
    assert (layout.width, layout.height, layout.cell_size_meters) == (12, 8, 0.5)
    assert len(layout.blocked_positions) == 5
    route = CableRouteService(layout).calculate_route("RACK-A23", "RACK-D17")
    assert route.steps == 14
    assert route.distance_meters == 7
    assert route.recommended_cable_length_meters == pytest.approx(7.7)


@pytest.mark.parametrize("field", ["width", "height", "cell_size_meters", "racks", "blocked_cells"])
def test_required_fields(tmp_path: Path, payload: dict, field: str) -> None:
    del payload[field]
    with pytest.raises(LayoutLoadError, match=field):
        load_layout(write_layout(tmp_path, payload))


@pytest.mark.parametrize(
    "changes",
    [
        {"width": "3"}, {"width": True}, {"height": 1.5}, {"width": 0},
        {"cell_size_meters": "0.5"}, {"cell_size_meters": True},
        {"cell_size_meters": 0}, {"cell_size_meters": -1},
        {"cell_size_meters": float("nan")}, {"cell_size_meters": float("inf")},
        {"unexpected": 1}, {"racks": {}}, {"racks": [None]},
        {"racks": [{"id": "A", "x": 0}]},
        {"racks": [{"id": "", "x": 0, "y": 0}]},
        {"racks": [{"id": 1, "x": 0, "y": 0}]},
        {"racks": [{"id": "A", "x": True, "y": 0}]},
        {"racks": [{"id": "A", "x": 0, "y": 0, "extra": 1}]},
        {"racks": [{"id": "A", "x": 3, "y": 0}]},
        {"racks": [{"id": "A", "x": 1, "y": 0}]},
        {"racks": [{"id": "A", "x": 0, "y": 0}, {"id": "A", "x": 2, "y": 0}]},
        {"blocked_cells": None}, {"blocked_cells": [[1]]},
        {"blocked_cells": [[1, 1, 1]]}, {"blocked_cells": [["1", 1]]},
        {"blocked_cells": [[1.5, 1]]}, {"blocked_cells": [[False, 1]]},
        {"blocked_cells": [[-1, 0]]}, {"blocked_cells": [[0, 3]]},
    ],
)
def test_malformed_layouts_are_rejected(tmp_path: Path, payload: dict, changes: dict) -> None:
    path = write_layout(tmp_path, payload | changes)
    with pytest.raises(LayoutLoadError) as caught:
        load_layout(path)
    assert str(path) in str(caught.value)
    assert caught.value.__cause__ is not None


@pytest.mark.parametrize("payload", [None, [], "layout", 42])
def test_top_level_must_be_an_object(tmp_path: Path, payload: object) -> None:
    with pytest.raises(LayoutLoadError):
        load_layout(write_layout(tmp_path, payload))


@pytest.mark.parametrize("contents", [b'{"width":', b"", b"\xff\xfe"])
def test_invalid_json_or_encoding(tmp_path: Path, contents: bytes) -> None:
    path = tmp_path / "broken.json"
    path.write_bytes(contents)
    with pytest.raises(LayoutLoadError, match="broken.json"):
        load_layout(path)


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(LayoutLoadError) as caught:
        load_layout(tmp_path / "missing.json")
    assert isinstance(caught.value.__cause__, FileNotFoundError)


def test_empty_collections_are_valid(tmp_path: Path, payload: dict) -> None:
    payload.update(racks=[], blocked_cells=[], cell_size_meters=1)
    layout = load_layout(write_layout(tmp_path, payload))
    assert layout.racks == ()
    assert layout.blocked_positions == frozenset()
    assert layout.cell_size_meters == 1

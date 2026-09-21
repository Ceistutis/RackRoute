"""Editing replaces only a valid in-memory layout and updates routing."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app


def test_edit_updates_racks_and_route_without_writing_json(tmp_path: Path) -> None:
    original = {
        "width": 3, "height": 2, "cell_size_meters": 0.5,
        "racks": [{"id": "A", "x": 0, "y": 0}, {"id": "B", "x": 2, "y": 0}],
        "blocked_cells": [],
    }
    path = tmp_path / "layout.json"
    path.write_text(json.dumps(original), encoding="utf-8")
    with TestClient(create_app(path)) as client:
        edited = original | {"blocked_cells": [[1, 0]], "racks": [*original["racks"], {"id": "C", "x": 2, "y": 1}]}
        response = client.put("/api/v1/layout", json=edited)
        assert response.status_code == 200
        assert response.json() == edited
        assert client.get("/api/v1/layout").json() == edited
        assert client.get("/api/v1/racks").json() == edited["racks"]
        route = client.post("/api/v1/cable-routes", json={"source_rack": "A", "destination_rack": "B"})
        assert route.status_code == 200
        assert route.json()["steps"] == 4
        assert [1, 0] not in route.json()["route"]
        assert client.post("/api/v1/cable-routes", json={"source_rack": "A", "destination_rack": "C"}).status_code == 200
        assert json.loads(path.read_text(encoding="utf-8")) == original
        removed = edited | {"racks": [edited["racks"][0]], "blocked_cells": []}
        assert client.put("/api/v1/layout", json=removed).status_code == 200
        assert client.post("/api/v1/cable-routes", json={"source_rack": "A", "destination_rack": "B"}).status_code == 404
    with TestClient(create_app(path)) as client:
        assert client.get("/api/v1/layout").json() == original


@pytest.mark.parametrize("changes", [
    {"width": 0}, {"width": True}, {"cell_size_meters": "0.5"},
    {"blocked_cells": [[12, 0]]}, {"blocked_cells": [[1, 1]]},
    {"blocked_cells": [[1]]}, {"blocked_cells": [[True, 0]]},
    {"racks": [{"id": "A", "x": -1, "y": 0}]},
    {"racks": [{"id": "A", "x": 0, "y": 0}, {"id": "A", "x": 1, "y": 0}]},
    {"racks": [{"id": "", "x": 0, "y": 0}]},
])
def test_invalid_edit_keeps_previous_layout(changes: dict) -> None:
    with TestClient(create_app()) as client:
        original = client.get("/api/v1/layout").json()
        assert client.put("/api/v1/layout", json=original | changes).status_code == 422
        assert client.get("/api/v1/layout").json() == original
        assert client.post("/api/v1/cable-routes", json={
            "source_rack": "RACK-A23", "destination_rack": "RACK-D17",
        }).status_code == 200


def test_empty_layout_can_be_populated() -> None:
    with TestClient(create_app()) as client:
        layout = client.get("/api/v1/layout").json() | {"racks": [], "blocked_cells": []}
        assert client.put("/api/v1/layout", json=layout).status_code == 200
        assert client.get("/api/v1/racks").json() == []
        layout["racks"] = [{"id": "NEW", "x": 0, "y": 0}]
        assert client.put("/api/v1/layout", json=layout).status_code == 200
        assert client.post("/api/v1/cable-routes", json={"source_rack": "NEW", "destination_rack": "NEW"}).json()["steps"] == 0

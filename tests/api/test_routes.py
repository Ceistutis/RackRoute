"""HTTP integration tests using real startup, JSON loading and A* searches."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from datacenter.infrastructure import LayoutLoadError


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as client:
        yield client


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("path,content_type", [
    ("/", "text/html"), ("/static/styles.css", "text/css"),
    ("/static/app.js", "javascript"),
])
def test_frontend_is_served(client: TestClient, path: str, content_type: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    assert content_type in response.headers["content-type"]
    assert response.content


def test_layout_and_racks_are_public_json(client: TestClient) -> None:
    racks = client.get("/api/v1/racks")
    layout = client.get("/api/v1/layout")
    assert racks.status_code == layout.status_code == 200
    assert racks.json() == [
        {"id": "RACK-A23", "x": 1, "y": 1},
        {"id": "RACK-D17", "x": 10, "y": 6},
    ]
    assert layout.json() == {
        "width": 12, "height": 8, "cell_size_meters": 0.5,
        "racks": racks.json(),
        "blocked_cells": [[4, 1], [4, 2], [4, 3], [5, 3], [6, 3]],
    }


@pytest.mark.parametrize("margin,expected", [(None, 7.7), (0.0, 7.0), (0.25, 8.75)])
def test_cable_route(client: TestClient, margin: float | None, expected: float) -> None:
    payload = {"source_rack": "RACK-A23", "destination_rack": "RACK-D17"}
    if margin is not None:
        payload["safety_margin"] = margin
    response = client.post("/api/v1/cable-routes", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert set(result) == {
        "source", "destination", "route", "steps", "distance_meters",
        "recommended_cable_length_meters", "explored_nodes", "algorithm", "heuristic",
    }
    assert result["source"] == "RACK-A23"
    assert result["destination"] == "RACK-D17"
    assert result["route"][0] == [1, 1]
    assert result["route"][-1] == [10, 6]
    assert result["steps"] == len(result["route"]) - 1 == 14
    assert result["distance_meters"] == 7
    assert result["recommended_cable_length_meters"] == pytest.approx(expected)
    assert result["algorithm"] == "A*"
    assert result["heuristic"] == "Manhattan"
    assert isinstance(result["explored_nodes"], int) and result["explored_nodes"] > 0
    blocked = client.get("/api/v1/layout").json()["blocked_cells"]
    assert all(position not in blocked for position in result["route"])
    assert all(abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
               for a, b in zip(result["route"], result["route"][1:]))


def test_cable_route_same_rack(client: TestClient) -> None:
    response = client.post("/api/v1/cable-routes", json={
        "source_rack": "RACK-A23", "destination_rack": "RACK-A23",
    })
    assert response.status_code == 200
    result = response.json()
    assert result["route"] == [[1, 1]]
    assert result["steps"] == result["distance_meters"] == result["recommended_cable_length_meters"] == 0


@pytest.mark.parametrize("field", ["source_rack", "destination_rack"])
def test_unknown_rack_is_404(client: TestClient, field: str) -> None:
    payload = {"source_rack": "RACK-A23", "destination_rack": "RACK-D17", field: "missing"}
    response = client.post("/api/v1/cable-routes", json=payload)
    assert response.status_code == 404
    assert response.json() == {"detail": "Rack not found: missing"}


def test_negative_margin_is_400(client: TestClient) -> None:
    response = client.post("/api/v1/cable-routes", json={
        "source_rack": "RACK-A23", "destination_rack": "RACK-D17", "safety_margin": -0.1,
    })
    assert response.status_code == 400
    assert "margin" in response.json()["detail"].lower()


@pytest.mark.parametrize("changes", [
    {"safety_margin": "0.1"}, {"safety_margin": True}, {"safety_margin": None},
    {"source_rack": ""}, {"source_rack": "  "}, {"destination_rack": 12}, {"unknown": 1},
])
def test_invalid_cable_request(client: TestClient, changes: dict) -> None:
    response = client.post("/api/v1/cable-routes", json={
        "source_rack": "RACK-A23", "destination_rack": "RACK-D17", **changes,
    })
    assert response.status_code == 422
    assert response.json()["detail"]


@pytest.mark.parametrize("contents", [
    '{"source_rack":', '{}',
    '{"source_rack":"RACK-A23","destination_rack":"RACK-D17","safety_margin":NaN}',
])
def test_malformed_json_and_nonfinite_input(client: TestClient, contents: str) -> None:
    response = client.post("/api/v1/cable-routes", content=contents, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["detail"]


@pytest.mark.parametrize("blocked,cost", [([], 2), ([[1, 0]], 4)])
def test_generic_route(client: TestClient, blocked: list, cost: int) -> None:
    response = client.post("/api/v1/routes", json={
        "width": 3, "height": 3, "start": [0, 0], "goal": [2, 0], "blocked_cells": blocked,
    })
    assert response.status_code == 200
    result = response.json()
    assert set(result) == {"route", "total_cost", "explored_nodes", "algorithm", "heuristic"}
    assert result["route"][0] == [0, 0] and result["route"][-1] == [2, 0]
    assert result["total_cost"] == len(result["route"]) - 1 == cost
    assert all(position not in blocked for position in result["route"])
    assert result["explored_nodes"] > 0


def test_generic_same_position(client: TestClient) -> None:
    response = client.post("/api/v1/routes", json={"width": 1, "height": 1, "start": [0, 0], "goal": [0, 0]})
    assert response.status_code == 200
    assert response.json()["route"] == [[0, 0]]
    assert response.json()["total_cost"] == 0


def test_generic_unreachable_goal(client: TestClient) -> None:
    response = client.post("/api/v1/routes", json={
        "width": 3, "height": 1, "start": [0, 0], "goal": [2, 0], "blocked_cells": [[1, 0]],
    })
    assert response.status_code == 422
    assert "No route" in response.json()["detail"]


@pytest.mark.parametrize("changes", [
    {"width": 0}, {"width": "3"}, {"height": True}, {"start": [-1, 0]},
    {"goal": [3, 0]}, {"start": [0]}, {"goal": [1.5, 0]},
    {"blocked_cells": [[0, 0]]}, {"blocked_cells": [[2, 0]]},
    {"blocked_cells": [[3, 1]]}, {"blocked_cells": [[1, 0, 2]]},
])
def test_invalid_generic_grid(client: TestClient, changes: dict) -> None:
    response = client.post("/api/v1/routes", json={
        "width": 3, "height": 3, "start": [0, 0], "goal": [2, 0], **changes,
    })
    assert response.status_code == 422


def test_disconnected_cable_route_and_load_once(tmp_path: Path) -> None:
    path = tmp_path / "layout.json"
    path.write_text(json.dumps({
        "width": 3, "height": 1, "cell_size_meters": 1,
        "racks": [{"id": "A", "x": 0, "y": 0}, {"id": "B", "x": 2, "y": 0}],
        "blocked_cells": [[1, 0]],
    }), encoding="utf-8")
    with TestClient(create_app(path)) as client:
        path.write_text("invalid after startup", encoding="utf-8")
        assert client.get("/api/v1/layout").status_code == 200
        response = client.post("/api/v1/cable-routes", json={"source_rack": "A", "destination_rack": "B"})
        assert response.status_code == 422
        assert "No route" in response.json()["detail"]
        # Generic routing uses its own grid, not the loaded Data Center layout.
        response = client.post("/api/v1/routes", json={
            "width": 3, "height": 1, "start": [0, 0], "goal": [2, 0],
        })
        assert response.status_code == 200


def test_invalid_layout_fails_startup(tmp_path: Path) -> None:
    with pytest.raises(LayoutLoadError):
        with TestClient(create_app(tmp_path / "missing.json")):
            pass


def test_openapi_documents_all_endpoints(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert set(response.json()["paths"]) == {
        "/health", "/api/v1/routes", "/api/v1/cable-routes", "/api/v1/racks", "/api/v1/layout",
    }
    assert client.get("/docs").status_code == 200

"""Service tests exercise the real layout and reusable A* engine."""

import pytest

from datacenter.exceptions import (
    CableRouteError,
    InvalidSafetyMarginError,
    NoRouteAvailableError,
    RackNotFoundError,
)
from datacenter.models import CableRoute, DataCenterLayout, Position, Rack
from datacenter.services import CableRouteService


@pytest.fixture
def layout() -> DataCenterLayout:
    return DataCenterLayout(
        width=3,
        height=3,
        cell_size_meters=0.5,
        racks=(Rack("A", Position(0, 0)), Rack("B", Position(2, 0))),
    )


def test_default_margin_and_domain_result(layout: DataCenterLayout) -> None:
    route = CableRouteService(layout).calculate_route("A", "B")
    assert isinstance(route, CableRoute)
    assert route.source_rack == layout.get_rack("A")
    assert route.destination_rack == layout.get_rack("B")
    assert route.path == (Position(0, 0), Position(1, 0), Position(2, 0))
    assert route.steps == 2
    assert route.distance_meters == pytest.approx(1.0)
    assert route.recommended_cable_length_meters == pytest.approx(1.1)
    assert route.explored_nodes == 3


@pytest.mark.parametrize("margin,expected", [(0, 1.0), (0.25, 1.25), (1.5, 2.5)])
def test_explicit_margin(layout: DataCenterLayout, margin: float, expected: float) -> None:
    route = CableRouteService(layout).calculate_route("A", "B", margin)
    assert route.recommended_cable_length_meters == pytest.approx(expected)


def test_distance_uses_detour_and_cell_size(layout: DataCenterLayout) -> None:
    blocked_layout = DataCenterLayout(
        3, 3, 0.75, layout.racks, frozenset({Position(1, 0)})
    )
    route = CableRouteService(blocked_layout).calculate_route("A", "B")
    assert route.steps == 4
    assert route.steps == len(route.path) - 1
    assert route.distance_meters == pytest.approx(3.0)
    assert route.recommended_cable_length_meters == pytest.approx(3.3)
    assert all(b in blocked_layout.neighbors(a) for a, b in zip(route.path, route.path[1:]))


@pytest.mark.parametrize("source,destination", [("missing", "B"), ("A", "missing")])
def test_missing_rack_raises_domain_error(
    layout: DataCenterLayout, source: str, destination: str
) -> None:
    with pytest.raises(RackNotFoundError) as caught:
        CableRouteService(layout).calculate_route(source, destination)
    assert caught.value.rack_id == "missing"
    assert isinstance(caught.value, CableRouteError)


def test_no_route_raises_domain_error(layout: DataCenterLayout) -> None:
    disconnected = DataCenterLayout(
        3, 3, 0.5, layout.racks, frozenset(Position(1, y) for y in range(3))
    )
    with pytest.raises(NoRouteAvailableError) as caught:
        CableRouteService(disconnected).calculate_route("A", "B")
    assert caught.value.source_rack_id == "A"
    assert caught.value.destination_rack_id == "B"
    assert isinstance(caught.value, CableRouteError)


def test_same_rack_returns_zero_length(layout: DataCenterLayout) -> None:
    route = CableRouteService(layout).calculate_route("A", "A")
    assert route.source_rack == route.destination_rack
    assert route.path == (Position(0, 0),)
    assert route.steps == 0
    assert route.distance_meters == 0
    assert route.recommended_cable_length_meters == 0
    assert route.explored_nodes == 1


def test_same_unknown_id_still_fails(layout: DataCenterLayout) -> None:
    with pytest.raises(RackNotFoundError):
        CableRouteService(layout).calculate_route("missing", "missing")


@pytest.mark.parametrize(
    "margin", [-0.01, float("nan"), float("inf"), -float("inf"), True, "0.10", None, 10**400],
    ids=["negative", "nan", "infinity", "negative-infinity", "boolean", "string", "none", "overflow"],
)
def test_invalid_margin_raises_domain_error(layout: DataCenterLayout, margin) -> None:
    with pytest.raises(InvalidSafetyMarginError):
        CableRouteService(layout).calculate_route("A", "B", margin)


def test_same_rack_does_not_bypass_margin_validation(layout: DataCenterLayout) -> None:
    with pytest.raises(InvalidSafetyMarginError):
        CableRouteService(layout).calculate_route("A", "A", -0.1)

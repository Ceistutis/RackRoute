"""Domain behavior and integration with the unchanged generic search engine."""

from dataclasses import FrozenInstanceError
from math import inf

import pytest

from datacenter.models import CableRoute, DataCenterLayout, Position, Rack
from pathfinding.astar import AStar
from pathfinding.graph import Graph
from pathfinding.manhattan import manhattan
from pathfinding.result import PathResult


def position_manhattan(current: Position, goal: Position) -> float:
    return manhattan(current.as_tuple(), goal.as_tuple())


def test_position_has_immutable_value_semantics() -> None:
    position = Position(1, 2)
    assert position == Position(1, 2)
    assert position != Position(2, 1)
    assert {position: "node"}[Position(1, 2)] == "node"
    assert position.as_tuple() == (1, 2)
    with pytest.raises(FrozenInstanceError):
        position.x = 3


@pytest.mark.parametrize("coordinate", [1.5, True, "1"])
def test_position_rejects_non_integer_coordinates(coordinate) -> None:
    with pytest.raises(ValueError, match="integers"):
        Position(coordinate, 0)


def test_rack_lookup() -> None:
    rack = Rack("A", Position(0, 0))
    layout = DataCenterLayout(2, 2, 0.5, racks=(rack,))
    assert layout.get_rack("A") == rack
    with pytest.raises(KeyError):
        layout.get_rack("missing")


@pytest.mark.parametrize("rack_id", ["", "  "])
def test_rack_requires_id(rack_id: str) -> None:
    with pytest.raises(ValueError, match="ID"):
        Rack(rack_id, Position(0, 0))


def test_neighbors_allow_only_four_orthogonal_moves() -> None:
    layout = DataCenterLayout(3, 3, 0.5)
    center = Position(1, 1)
    assert set(layout.neighbors(center)) == {
        Position(1, 0), Position(1, 2), Position(0, 1), Position(2, 1)
    }
    assert all(layout.cost(center, neighbor) == 1 for neighbor in layout.neighbors(center))


def test_neighbors_respect_boundaries_and_blocks() -> None:
    layout = DataCenterLayout(3, 3, 0.5, blocked_positions=frozenset({Position(1, 0)}))
    assert set(layout.neighbors(Position(0, 0))) == {Position(0, 1)}
    assert set(layout.neighbors(Position(2, 2))) == {Position(1, 2), Position(2, 1)}
    assert list(layout.neighbors(Position(1, 0))) == []
    assert list(layout.neighbors(Position(-1, 0))) == []


@pytest.mark.parametrize(
    "current,neighbor",
    [(Position(0, 0), Position(1, 1)), (Position(0, 0), Position(2, 0)),
     (Position(0, 0), Position(0, 0)), (Position(0, 0), Position(-1, 0)),
     (Position(0, 0), Position(1, 0)), (Position(1, 0), Position(0, 0))],
)
def test_cost_rejects_invalid_edges(current: Position, neighbor: Position) -> None:
    layout = DataCenterLayout(3, 3, 1, blocked_positions=frozenset({Position(1, 0)}))
    with pytest.raises(ValueError, match="Movement"):
        layout.cost(current, neighbor)


@pytest.mark.parametrize(
    "changes",
    [{"width": 0}, {"height": -1}, {"width": 1.5}, {"height": True},
     {"cell_size_meters": 0}, {"cell_size_meters": -1},
     {"cell_size_meters": inf}, {"cell_size_meters": float("nan")},
     {"blocked_positions": {Position(3, 0)}},
     {"racks": (Rack("A", Position(-1, 0)),)},
     {"racks": (Rack("A", Position(0, 0)), Rack("A", Position(1, 0)))},
     {"racks": (Rack("A", Position(0, 0)),), "blocked_positions": {Position(0, 0)}}],
)
def test_invalid_layout_is_rejected(changes) -> None:
    values = {"width": 3, "height": 3, "cell_size_meters": 0.5}
    with pytest.raises(ValueError):
        DataCenterLayout(**(values | changes))


def test_layout_copies_input_collections() -> None:
    racks = [Rack("A", Position(0, 0))]
    blocked = {Position(1, 0)}
    layout = DataCenterLayout(3, 3, 0.5, racks, blocked)
    racks.clear()
    blocked.clear()
    assert len(layout.racks) == 1
    assert not layout.is_walkable(Position(1, 0))


@pytest.mark.parametrize(
    "blocked,expected_cost", [(frozenset(), 2), (frozenset({Position(1, 0)}), 4)]
)
def test_layout_works_with_existing_astar(blocked, expected_cost: int) -> None:
    source = Rack("A", Position(0, 0))
    destination = Rack("B", Position(2, 0))
    layout = DataCenterLayout(3, 3, 0.5, (source, destination), blocked)
    graph: Graph[Position] = layout
    result = AStar.search(graph, source.position, destination.position, position_manhattan)
    assert result.path[0] == source.position
    assert result.path[-1] == destination.position
    assert result.total_cost == expected_cost
    assert len(result.path) - 1 == expected_cost
    assert all(b in layout.neighbors(a) for a, b in zip(result.path, result.path[1:]))


def test_layout_can_have_disconnected_racks() -> None:
    layout = DataCenterLayout(
        3, 3, 0.5, blocked_positions=frozenset(Position(1, y) for y in range(3))
    )
    result = AStar.search(layout, Position(0, 0), Position(2, 0), position_manhattan)
    assert result.path == []
    assert result.total_cost == inf


def test_cable_route_is_a_domain_result() -> None:
    source = Rack("A", Position(0, 0))
    destination = Rack("B", Position(1, 0))
    path = [source.position, destination.position]
    route = CableRoute(source, destination, path, 1, 0.5, 0.55, 2)
    path.clear()
    assert route.source_rack == source
    assert route.destination_rack == destination
    assert route.path == (source.position, destination.position)
    assert route.steps == 1
    assert route.distance_meters == 0.5
    assert route.recommended_cable_length_meters == 0.55
    assert route.explored_nodes == 2
    assert not isinstance(route, PathResult)

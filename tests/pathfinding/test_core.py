"""Behavioral tests using graphs with no Data Center dependencies."""

from collections.abc import Hashable, Iterable
from dataclasses import dataclass
from math import inf
from pathlib import Path
import subprocess
import sys
from typing import Generic, TypeVar

import pytest

from pathfinding.astar import AStar
from pathfinding.manhattan import manhattan


Node = TypeVar("Node", bound=Hashable)
Coordinate = tuple[int, int]


class WeightedGraph(Generic[Node]):
    def __init__(self, edges: dict[Node, dict[Node, float]]) -> None:
        self.edges = edges

    def neighbors(self, node: Node) -> Iterable[Node]:
        return self.edges.get(node, {})

    def cost(self, current: Node, neighbor: Node) -> float:
        return self.edges[current][neighbor]


class Grid:
    def __init__(self, blocked: set[Coordinate]) -> None:
        self.blocked = blocked

    def neighbors(self, node: Coordinate) -> Iterable[Coordinate]:
        x, y = node
        for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            nx, ny = neighbor
            if 0 <= nx < 3 and 0 <= ny < 3 and neighbor not in self.blocked:
                yield neighbor

    def cost(self, current: Coordinate, neighbor: Coordinate) -> float:
        return 1.0


@pytest.mark.parametrize(
    "start,goal,expected",
    [((0, 0), (3, 4), 7), ((-2, 3), (1, -1), 7), ((2, 2), (2, 2), 0)],
)
def test_manhattan(start, goal, expected):
    assert manhattan(start, goal) == expected
    assert manhattan(goal, start) == expected


@pytest.mark.parametrize(
    "blocked,expected",
    [(set(), 2), ({(1, 0)}, 4)],
    ids=["direct-path", "path-around-obstacle"],
)
def test_grid_route(blocked, expected):
    result = AStar.search(Grid(blocked), (0, 0), (2, 0), manhattan)
    assert result.path[0] == (0, 0)
    assert result.path[-1] == (2, 0)
    assert result.total_cost == expected
    assert len(result.path) - 1 == expected
    assert not blocked.intersection(result.path)
    assert all(manhattan(a, b) == 1 for a, b in zip(result.path, result.path[1:]))


def test_unreachable_goal():
    result = AStar.search(Grid({(1, 0), (1, 1), (1, 2)}), (0, 0), (2, 0), manhattan)
    assert result.path == []
    assert result.total_cost == inf
    assert result.explored_nodes == 3


def test_same_start_and_goal():
    result = AStar.search(WeightedGraph({}), "a", "a", lambda a, b: 0.0)
    assert result.path == ["a"]
    assert result.total_cost == 0
    assert result.explored_nodes == 1


def test_weighted_route_and_stale_queue_entries():
    graph = WeightedGraph({"s": {"a": 5, "b": 1}, "b": {"a": 1}, "a": {"g": 10}})
    result = AStar.search(graph, "s", "g", lambda a, b: 0.0)
    assert result.path == ["s", "b", "a", "g"]
    assert result.total_cost == 12
    assert result.explored_nodes == 4


def test_reopens_nodes_with_admissible_inconsistent_heuristic():
    graph = WeightedGraph({"s": {"a": 3, "b": 1}, "b": {"a": 1}, "a": {"g": 3}})
    estimates = {"s": 0, "a": 0, "b": 4, "g": 0}
    result = AStar.search(graph, "s", "g", lambda a, b: estimates[a])
    assert result.path == ["s", "b", "a", "g"]
    assert result.total_cost == 5
    assert result.explored_nodes == 5


def test_equal_priorities_do_not_require_orderable_nodes():
    @dataclass(frozen=True)
    class Vertex:
        name: str

    s, a, b, g = (Vertex(name) for name in "sabg")
    graph = WeightedGraph({s: {a: 1, b: 1}, a: {g: 1}, b: {g: 1}})
    result = AStar.search(graph, s, g, lambda a, b: 0.0)
    assert result.path in ([s, a, g], [s, b, g])
    assert result.total_cost == 2


def test_zero_cost_cycle_terminates():
    graph = WeightedGraph({"s": {"a": 0}, "a": {"s": 0, "g": 1}})
    result = AStar.search(graph, "s", "g", lambda a, b: 0.0)
    assert result.path == ["s", "a", "g"]
    assert result.total_cost == 1


@pytest.mark.parametrize("cost", [-1, inf, float("nan")])
def test_rejects_invalid_edge_costs(cost):
    with pytest.raises(ValueError, match="finite and non-negative"):
        AStar.search(WeightedGraph({"s": {"g": cost}}), "s", "g", lambda a, b: 0.0)


@pytest.mark.parametrize("branches", [("a", "b"), ("b", "a")])
def test_multiple_equivalent_shortest_paths(branches: tuple[str, str]) -> None:
    graph = WeightedGraph(
        {"s": dict.fromkeys(branches, 1.0), "a": {"g": 1.0}, "b": {"g": 1.0}}
    )
    result = AStar.search(graph, "s", "g", lambda a, b: 0.0)
    # Either optimum is valid, regardless of neighbor enumeration order.
    assert result.path in (["s", "a", "g"], ["s", "b", "g"])
    assert result.total_cost == 2.0


def test_total_cost_sums_edge_weights_instead_of_counting_steps() -> None:
    graph = WeightedGraph({"s": {"g": 2.0, "a": 0.25}, "a": {"g": 0.5}})
    result = AStar.search(graph, "s", "g", lambda a, b: 0.0)
    assert result.path == ["s", "a", "g"]
    assert result.total_cost == pytest.approx(0.75)
    assert result.total_cost == pytest.approx(
        sum(graph.cost(a, b) for a, b in zip(result.path, result.path[1:]))
    )


def test_explored_nodes_includes_start_and_goal() -> None:
    graph = WeightedGraph({"s": {"a": 1.0}, "a": {"g": 1.0}})
    result = AStar.search(graph, "s", "g", lambda a, b: 0.0)
    assert isinstance(result.explored_nodes, int)
    assert result.explored_nodes == 3


def test_core_runs_without_application_packages(tmp_path: Path) -> None:
    """Run a copied core with no application packages or site dependencies."""
    import shutil

    import pathfinding

    core_directory = Path(pathfinding.__file__).parent
    shutil.copytree(core_directory, tmp_path / "pathfinding", ignore=shutil.ignore_patterns("__pycache__"))
    script = """
import sys
sys.path.insert(0, sys.argv[1])
from pathfinding.astar import AStar
from pathfinding.manhattan import manhattan

class Graph:
    def neighbors(self, node):
        return [(1, 0)] if node == (0, 0) else []
    def cost(self, current, neighbor):
        return 1.0

result = AStar.search(Graph(), (0, 0), (1, 0), manhattan)
assert result.path == [(0, 0), (1, 0)]
assert result.total_cost == 1.0
assert result.explored_nodes == 2
assert not {'datacenter', 'api', 'frontend'}.intersection(sys.modules)
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

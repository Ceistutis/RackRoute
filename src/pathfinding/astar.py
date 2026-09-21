"""A* search using only generic graph and heuristic contracts."""

import heapq
from itertools import count
from math import inf, isfinite

from .graph import Graph, Node
from .heuristic import Heuristic
from .result import PathResult


class AStar:
    """Search finite graphs with non-negative costs and admissible heuristics.

    The heuristic must be finite and zero at the goal. Nodes need stable hashing
    and equality, but do not need ordering. A zero heuristic gives Dijkstra search.
    """

    @staticmethod
    def search(
        graph: Graph[Node],
        start: Node,
        goal: Node,
        heuristic: Heuristic[Node],
    ) -> PathResult[Node]:
        sequence = count()
        # The unique counter breaks priority ties without comparing nodes.
        frontier: list[tuple[float, int, float, Node]] = [
            (heuristic(start, goal), next(sequence), 0.0, start)
        ]
        costs: dict[Node, float] = {start: 0.0}
        parents: dict[Node, Node] = {}
        explored_nodes = 0

        while frontier:
            _, _, current_cost, current = heapq.heappop(frontier)
            if current_cost != costs[current]:
                continue  # A cheaper entry superseded this queue entry.
            explored_nodes += 1

            if current == goal:
                path = [current]
                while current in parents:
                    current = parents[current]
                    path.append(current)
                path.reverse()
                return PathResult(path, current_cost, explored_nodes)

            for neighbor in graph.neighbors(current):
                edge_cost = graph.cost(current, neighbor)
                if not isfinite(edge_cost) or edge_cost < 0:
                    raise ValueError("Edge costs must be finite and non-negative")
                candidate_cost = current_cost + edge_cost
                if candidate_cost < costs.get(neighbor, inf):
                    costs[neighbor] = candidate_cost
                    parents[neighbor] = current
                    priority = candidate_cost + heuristic(neighbor, goal)
                    heapq.heappush(
                        frontier,
                        (priority, next(sequence), candidate_cost, neighbor),
                    )

        return PathResult([], inf, explored_nodes)

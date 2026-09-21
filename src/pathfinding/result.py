"""Domain-independent search result."""

from dataclasses import dataclass
from typing import Generic

from .graph import Node


@dataclass(frozen=True)
class PathResult(Generic[Node]):
    """A path includes both endpoints; an empty path means unreachable.

    Unreachable results have infinite total_cost. explored_nodes counts valid
    queue removals, including the goal and any nodes reopened at a lower cost.
    """

    path: list[Node]
    total_cost: float
    explored_nodes: int

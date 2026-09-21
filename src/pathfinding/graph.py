"""Minimal graph contract used by A*."""

from collections.abc import Hashable, Iterable
from typing import Protocol, TypeVar

Node = TypeVar("Node", bound=Hashable)


class Graph(Protocol[Node]):
    """Nodes must be hashable; edge costs must be finite and non-negative."""

    def neighbors(self, node: Node) -> Iterable[Node]: ...

    def cost(self, current: Node, neighbor: Node) -> float: ...

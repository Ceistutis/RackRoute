"""A generic orthogonal grid adapter for coordinate-based searches."""

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Grid:
    """Grid adapter; callers validate dimensions, endpoints and blocked cells."""

    width: int
    height: int
    blocked: frozenset[tuple[int, int]] = frozenset()

    def neighbors(self, node: tuple[int, int]) -> Iterable[tuple[int, int]]:
        x, y = node
        for neighbor in ((x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)):
            nx, ny = neighbor
            if 0 <= nx < self.width and 0 <= ny < self.height and neighbor not in self.blocked:
                yield neighbor

    def cost(self, current: tuple[int, int], neighbor: tuple[int, int]) -> float:
        return 1.0

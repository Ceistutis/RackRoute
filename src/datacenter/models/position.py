"""Immutable grid coordinates."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    x: int
    y: int

    def __post_init__(self) -> None:
        if type(self.x) is not int or type(self.y) is not int:
            raise ValueError("Position coordinates must be integers")

    def as_tuple(self) -> tuple[int, int]:
        """Expose coordinates to generic functions such as Manhattan distance."""
        return self.x, self.y

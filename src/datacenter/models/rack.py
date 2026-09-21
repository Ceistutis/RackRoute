"""A rack identified by its ID and grid position."""

from dataclasses import dataclass

from .position import Position


@dataclass(frozen=True)
class Rack:
    id: str
    position: Position

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Rack ID must be a non-empty string")

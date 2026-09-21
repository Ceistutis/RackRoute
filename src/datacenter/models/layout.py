"""Data Center layout exposing the generic graph contract structurally."""

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite

from .position import Position
from .rack import Rack


@dataclass(frozen=True)
class DataCenterLayout:
    """A fixed grid; rack cells are traversable unless explicitly blocked.

    Coordinates range from zero to width/height minus one. Collections are
    copied into immutable containers so validated layout rules remain stable.
    """

    width: int
    height: int
    cell_size_meters: float
    racks: tuple[Rack, ...] = ()
    blocked_positions: frozenset[Position] = frozenset()

    def __post_init__(self) -> None:
        if any(type(size) is not int or size <= 0 for size in (self.width, self.height)):
            raise ValueError("Layout dimensions must be positive integers")
        if not isfinite(self.cell_size_meters) or self.cell_size_meters <= 0:
            raise ValueError("Cell size must be finite and positive")
        object.__setattr__(self, "racks", tuple(self.racks))
        object.__setattr__(self, "blocked_positions", frozenset(self.blocked_positions))
        if any(not self.contains(position) for position in self.blocked_positions):
            raise ValueError("Blocked positions must be inside the layout")
        ids = set()
        for rack in self.racks:
            if rack.id in ids:
                raise ValueError(f"Duplicate rack ID: {rack.id}")
            if not self.is_walkable(rack.position):
                raise ValueError(f"Rack {rack.id} must occupy an unblocked position inside the layout")
            ids.add(rack.id)

    def contains(self, position: Position) -> bool:
        return 0 <= position.x < self.width and 0 <= position.y < self.height

    def is_walkable(self, position: Position) -> bool:
        return self.contains(position) and position not in self.blocked_positions

    def get_rack(self, rack_id: str) -> Rack:
        """Look up a rack; raise KeyError for an unknown ID."""
        for rack in self.racks:
            if rack.id == rack_id:
                return rack
        raise KeyError(rack_id)

    def neighbors(self, node: Position) -> Iterable[Position]:
        if not self.is_walkable(node):
            return
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            neighbor = Position(node.x + dx, node.y + dy)
            if self.is_walkable(neighbor):
                yield neighbor

    def cost(self, current: Position, neighbor: Position) -> float:
        """Return unit cost for a valid edge, rejecting invalid transitions."""
        adjacent = abs(current.x - neighbor.x) + abs(current.y - neighbor.y) == 1
        if not adjacent or not self.is_walkable(current) or not self.is_walkable(neighbor):
            raise ValueError("Movement requires adjacent, unblocked positions inside the layout")
        return 1.0

"""Domain result expressed in racks, positions and physical cable lengths."""

from dataclasses import dataclass

from .position import Position
from .rack import Rack


@dataclass(frozen=True)
class CableRoute:
    """Successful cable route, assembled by the application service.

    The path includes both rack positions. Steps count movements, not positions.
    Physical lengths and safety margin calculation belong to the service.
    """

    source_rack: Rack
    destination_rack: Rack
    path: tuple[Position, ...]
    steps: int
    distance_meters: float
    recommended_cable_length_meters: float
    explored_nodes: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", tuple(self.path))

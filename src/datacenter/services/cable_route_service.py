"""Calculate a physical cable route using the reusable pathfinding core."""

from math import isfinite

from pathfinding.astar import AStar
from pathfinding.manhattan import manhattan

from datacenter.exceptions import (
    InvalidSafetyMarginError,
    NoRouteAvailableError,
    RackNotFoundError,
)
from datacenter.models import CableRoute, DataCenterLayout, Rack


class CableRouteService:
    def __init__(self, layout: DataCenterLayout) -> None:
        self.layout = layout

    def calculate_route(
        self,
        source_rack_id: str,
        destination_rack_id: str,
        safety_margin: float = 0.10,
    ) -> CableRoute:
        """Calculate a route; margin is a fraction (0.10 means 10%).

        Validate the margin first, then source and destination IDs. There is no
        upper percentage limit. Unknown racks and unreachable destinations raise
        domain errors; routing a rack to itself returns a zero-length route.
        """
        if (
            isinstance(safety_margin, bool)
            or not isinstance(safety_margin, (int, float))
            or safety_margin < 0
        ):
            raise InvalidSafetyMarginError("Safety margin must be finite and non-negative")
        try:
            finite_margin = isfinite(safety_margin)
        except OverflowError:
            finite_margin = False
        if not finite_margin:
            raise InvalidSafetyMarginError("Safety margin must be finite and non-negative")

        source = self._get_rack(source_rack_id)
        destination = self._get_rack(destination_rack_id)
        result = AStar.search(
            self.layout,
            source.position,
            destination.position,
            lambda current, goal: manhattan(current.as_tuple(), goal.as_tuple()),
        )
        if not result.path:
            raise NoRouteAvailableError(source_rack_id, destination_rack_id)

        steps = len(result.path) - 1
        distance_meters = steps * self.layout.cell_size_meters
        return CableRoute(
            source_rack=source,
            destination_rack=destination,
            path=tuple(result.path),
            steps=steps,
            distance_meters=distance_meters,
            recommended_cable_length_meters=distance_meters * (1 + safety_margin),
            explored_nodes=result.explored_nodes,
        )

    def _get_rack(self, rack_id: str) -> Rack:
        try:
            return self.layout.get_rack(rack_id)
        except KeyError as error:
            raise RackNotFoundError(rack_id) from error

"""Domain errors, independent from HTTP and application frameworks."""


class CableRouteError(Exception):
    """Base error for cable routing failures."""


class RackNotFoundError(CableRouteError):
    def __init__(self, rack_id: str) -> None:
        self.rack_id = rack_id
        super().__init__(f"Rack not found: {rack_id}")


class NoRouteAvailableError(CableRouteError):
    def __init__(self, source_rack_id: str, destination_rack_id: str) -> None:
        self.source_rack_id = source_rack_id
        self.destination_rack_id = destination_rack_id
        super().__init__(f"No route available from {source_rack_id} to {destination_rack_id}")


class InvalidSafetyMarginError(CableRouteError):
    """The safety margin is not a finite, non-negative number."""

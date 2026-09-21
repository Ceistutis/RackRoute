"""Explicit public JSON contracts, separate from domain objects."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator

Coordinate = Annotated[list[StrictInt], Field(min_length=2, max_length=2)]
PositiveInt = Annotated[StrictInt, Field(gt=0)]


class CableRouteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_rack: Annotated[StrictStr, Field(min_length=1, pattern=r"\S")]
    destination_rack: Annotated[StrictStr, Field(min_length=1, pattern=r"\S")]
    safety_margin: Annotated[float, Field(strict=True, allow_inf_nan=False)] = 0.10


class RouteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: PositiveInt
    height: PositiveInt
    start: Coordinate
    goal: Coordinate
    blocked_cells: list[Coordinate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_positions(self) -> Self:
        for x, y in [self.start, self.goal, *self.blocked_cells]:
            if not (0 <= x < self.width and 0 <= y < self.height):
                raise ValueError("All positions must be inside the grid")
        if self.start in self.blocked_cells or self.goal in self.blocked_cells:
            raise ValueError("Start and goal must not be blocked")
        return self


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class RouteResponse(BaseModel):
    route: list[Coordinate]
    total_cost: float
    explored_nodes: int
    algorithm: Literal["A*"] = "A*"
    heuristic: Literal["Manhattan"] = "Manhattan"


class CableRouteResponse(BaseModel):
    source: str
    destination: str
    route: list[Coordinate]
    steps: int
    distance_meters: float
    recommended_cable_length_meters: float
    explored_nodes: int
    algorithm: Literal["A*"] = "A*"
    heuristic: Literal["Manhattan"] = "Manhattan"


class RackResponse(BaseModel):
    id: str
    x: int
    y: int


class LayoutResponse(BaseModel):
    width: int
    height: int
    cell_size_meters: float
    racks: list[RackResponse]
    blocked_cells: list[Coordinate]


class RackInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Annotated[StrictStr, Field(min_length=1, pattern=r"\S")]
    x: StrictInt
    y: StrictInt


class LayoutUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    width: PositiveInt
    height: PositiveInt
    cell_size_meters: Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
    racks: list[RackInput]
    blocked_cells: list[Coordinate]

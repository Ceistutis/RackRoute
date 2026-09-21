"""HTTP endpoints and explicit domain-to-schema conversion."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from datacenter.models import DataCenterLayout, Position, Rack
from datacenter.services import CableRouteService
from pathfinding.astar import AStar
from pathfinding.grid import Grid
from pathfinding.manhattan import manhattan

from .dependencies import get_cable_route_service, get_layout
from .schemas import (
    CableRouteRequest, CableRouteResponse, HealthResponse, LayoutResponse,
    RackResponse, RouteRequest, RouteResponse, LayoutUpdateRequest,
)

router = APIRouter()
LayoutDependency = Annotated[DataCenterLayout, Depends(get_layout)]
ServiceDependency = Annotated[CableRouteService, Depends(get_cable_route_service)]


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse()


@router.post("/api/v1/routes", response_model=RouteResponse, tags=["routes"])
def calculate_route(payload: RouteRequest) -> RouteResponse:
    grid = Grid(payload.width, payload.height, frozenset(tuple(cell) for cell in payload.blocked_cells))
    result = AStar.search(grid, tuple(payload.start), tuple(payload.goal), manhattan)
    if not result.path:
        raise HTTPException(status_code=422, detail="No route available between start and goal")
    return RouteResponse(
        route=[list(position) for position in result.path],
        total_cost=result.total_cost,
        explored_nodes=result.explored_nodes,
    )


@router.post("/api/v1/cable-routes", response_model=CableRouteResponse, tags=["routes"])
def calculate_cable_route(payload: CableRouteRequest, service: ServiceDependency) -> CableRouteResponse:
    route = service.calculate_route(payload.source_rack, payload.destination_rack, payload.safety_margin)
    return CableRouteResponse(
        source=route.source_rack.id,
        destination=route.destination_rack.id,
        route=[[position.x, position.y] for position in route.path],
        steps=route.steps,
        distance_meters=route.distance_meters,
        recommended_cable_length_meters=route.recommended_cable_length_meters,
        explored_nodes=route.explored_nodes,
    )


@router.get("/api/v1/racks", response_model=list[RackResponse], tags=["layout"])
def list_racks(layout: LayoutDependency) -> list[RackResponse]:
    return [RackResponse(id=rack.id, x=rack.position.x, y=rack.position.y) for rack in layout.racks]


@router.get("/api/v1/layout", response_model=LayoutResponse, tags=["layout"])
def get_layout_response(layout: LayoutDependency) -> LayoutResponse:
    return LayoutResponse(
        width=layout.width,
        height=layout.height,
        cell_size_meters=layout.cell_size_meters,
        racks=list_racks(layout),
        blocked_cells=sorted([position.x, position.y] for position in layout.blocked_positions),
    )


@router.put("/api/v1/layout", response_model=LayoutResponse, tags=["layout"])
async def update_layout(payload: LayoutUpdateRequest, request: Request) -> LayoutResponse:
    """Replace the in-memory layout only after validating the complete edit."""
    try:
        layout = DataCenterLayout(
            payload.width, payload.height, payload.cell_size_meters,
            tuple(Rack(rack.id, Position(rack.x, rack.y)) for rack in payload.racks),
            frozenset(Position(x, y) for x, y in payload.blocked_cells),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    request.app.state.layout = layout
    request.app.state.cable_route_service = CableRouteService(layout)
    return get_layout_response(layout)

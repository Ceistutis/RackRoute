"""Access objects composed during application startup."""

from fastapi import Request

from datacenter.models import DataCenterLayout
from datacenter.services import CableRouteService


def get_layout(request: Request) -> DataCenterLayout:
    return request.app.state.layout


def get_cable_route_service(request: Request) -> CableRouteService:
    return request.app.state.cable_route_service

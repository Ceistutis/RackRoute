"""Adapters for loading Data Center layouts from external sources."""

from .layout_loader import LayoutLoadError, load_layout

__all__ = ["LayoutLoadError", "load_layout"]

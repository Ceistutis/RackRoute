"""Heuristic function contract, independent from any graph representation."""

from collections.abc import Callable
from typing import TypeAlias

from .graph import Node

# For optimal paths, estimates must be admissible and zero at the goal.
Heuristic: TypeAlias = Callable[[Node, Node], float]

"""Manhattan distance for two-dimensional coordinates."""


def manhattan(current: tuple[int, int], goal: tuple[int, int]) -> float:
    """Estimate distance on an orthogonal grid with unit movement costs.

    For other cost scales or movement rules, supply a suitable heuristic to A*.
    """
    return float(abs(current[0] - goal[0]) + abs(current[1] - goal[1]))

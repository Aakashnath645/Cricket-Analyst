from __future__ import annotations


def overs_to_balls(overs_value: float) -> int:
    """Convert overs to balls, supporting cricket notation and decimal overs.

    Cricket notation: 8.3 means 8 overs and 3 balls.
    Decimal overs: 8.75 means 8.75 overs (53 balls).
    """
    overs_value = max(overs_value, 0.0)
    whole_overs = int(overs_value)
    fractional = overs_value - whole_overs

    # If input is one decimal place and <= 6, treat as cricket score notation.
    # Some feeds represent over completion as x.6 (e.g., 19.6 for 20 overs).
    scaled = fractional * 10
    nearest = round(scaled)
    if abs(scaled - nearest) < 1e-9 and 0 <= nearest <= 6:
        return whole_overs * 6 + int(nearest)

    # Otherwise treat as decimal overs.
    return int(round(overs_value * 6))


def balls_to_overs_float(balls: int) -> float:
    balls = max(balls, 0)
    return balls / 6.0

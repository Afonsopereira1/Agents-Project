"""Movimento base na grelha, primeiro em x e depois em y, sem obstáculos."""

from math import floor, isfinite

from isia.domain.models import Position


def nonnegative(value: float, name: str) -> None:
    try:
        valid = type(value) in (int, float) and value >= 0 and isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{name} deve ser finito e não negativo.")


def position_at(origin: Position, target: Position, speed: float, elapsed: float) -> Position:
    """Células completas percorridas; não ultrapassa o destino nem perde frações."""
    if not isinstance(origin, Position) or not isinstance(target, Position):
        raise TypeError("A origem e o destino devem ser Position.")
    nonnegative(speed, "speed")
    nonnegative(elapsed, "elapsed")
    dx, dy = target.x - origin.x, target.y - origin.y
    distance = abs(dx) + abs(dy)
    if speed == 0 or elapsed == 0 or distance == 0:
        return origin
    # Limitar antes de multiplicar também evita overflow em durações grandes.
    steps = distance if elapsed >= distance / speed else floor(speed * elapsed)
    x_steps = min(steps, abs(dx))
    y_steps = min(steps - x_steps, abs(dy))
    return Position(origin.x + (x_steps if dx >= 0 else -x_steps),
                    origin.y + (y_steps if dy >= 0 else -y_steps))

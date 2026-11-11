"""Critérios locais e configuráveis para corroborar observações.

The compatibility check deliberately uses only the two observations and the
configured limits. It does not inspect simulator ground truth or real events.
"""

from math import hypot, isfinite

from isia.domain.models import Observation


def are_observations_compatible(
    first: Observation,
    second: Observation,
    max_distance: float,
    max_time_difference: float,
) -> bool:
    """Return whether two observations can refer to the same occurrence.

    Args:
        first: The first sensor observation.
        second: The second sensor observation.
        max_distance: Inclusive maximum Euclidean distance between positions.
        max_time_difference: Inclusive maximum absolute difference between
            observation instants, in the same simulated time unit as
            ``Observation.observed_at``.

    Returns:
        ``True`` when the observations have different ``event_id`` values and
        both configured limits are satisfied; otherwise ``False``.

    Raises:
        TypeError: If either observation or a limit has an invalid type.
        ValueError: If a limit is negative or not finite.
    """
    _validate_observation(first, "first")
    _validate_observation(second, "second")
    _validate_limit(max_distance, "max_distance")
    _validate_limit(max_time_difference, "max_time_difference")

    if first.event_id == second.event_id:
        return False

    distance = hypot(
        first.position.x - second.position.x,
        first.position.y - second.position.y,
    )
    time_difference = abs(first.observed_at - second.observed_at)

    return distance <= max_distance and time_difference <= max_time_difference


def _validate_observation(observation: Observation, name: str) -> None:
    if not isinstance(observation, Observation):
        raise TypeError(f"{name} must be an Observation.")


def _validate_limit(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite non-negative number.")
    if not isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite non-negative number.")

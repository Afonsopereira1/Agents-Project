"""Critérios locais e configuráveis para corroborar observações.

The compatibility check deliberately uses only the two observations and the
configured limits. It does not inspect simulator ground truth or real events.
"""

from collections.abc import Mapping
from math import hypot, isfinite

from isia.communication.messages import Message, MessageType, model_from_dict
from isia.domain.models import Observation
from isia.domain.models import Position
from isia.simulation.scenario import Source


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


def select_eligible_sources(
    observation: Observation,
    sensor_positions: Mapping[str, Position],
    source_profiles: Mapping[str, Source],
) -> tuple[str, ...]:
    """Return sensor IDs that can independently help verify an observation.

    A source is eligible when it has a known position and ``Source`` profile,
    is not the source of ``observation``, and the observation position is at
    most its configured detection range away. The distance comparison is
    inclusive. Source modalities are deliberately not compared with the
    observation type, so acoustic, visual and human sources may complement
    one another.

    Only the supplied sensor metadata is used: this function does not inspect
    simulator events, ground truth or another source's observation history.
    Identifiers are returned once, in lexicographic order.
    """
    if not isinstance(observation, Observation):
        raise TypeError("observation must be an Observation.")
    if not isinstance(sensor_positions, Mapping):
        raise TypeError("sensor_positions must be a mapping.")
    if not isinstance(source_profiles, Mapping):
        raise TypeError("source_profiles must be a mapping.")

    eligible = []
    for sensor_id in sorted(set(sensor_positions) & set(source_profiles)):
        if sensor_id == observation.source_id:
            continue

        position = sensor_positions[sensor_id]
        profile = source_profiles[sensor_id]
        if not isinstance(position, Position):
            raise TypeError("Each sensor position must be a Position.")
        if not isinstance(profile, Source):
            raise TypeError("Each source profile must be a Source.")

        distance = hypot(
            observation.position.x - position.x,
            observation.position.y - position.y,
        )
        if distance <= profile.detection_range:
            eligible.append(sensor_id)

    return tuple(eligible)


def classify_verification_response(
    initial_observation: Observation,
    response: Message,
    max_distance: float,
    max_time_difference: float,
) -> dict[str, object]:
    """Classify evidence in a validated ``VERIFY_RESPONSE``.

    The returned dictionary contains ``classification`` and the unique
    ``observation_ids`` used for that classification. Possible classifications
    in the current contract are ``compatible``, ``inconclusive`` and
    ``no_data``. ``contradictory`` and ``informative_absence`` remain
    conceptual categories until a response contract carries enough explicit
    information to distinguish them safely.

    A compatible result requires an observation with a different ``event_id``
    and a different ``source_id`` from the initial observation, and satisfying
    :func:`are_observations_compatible`. Repeated ``event_id`` values are
    evaluated only once. No simulator state or ground truth is consulted.
    """
    _validate_observation(initial_observation, "initial_observation")
    _validate_limit(max_distance, "max_distance")
    _validate_limit(max_time_difference, "max_time_difference")
    observations, status = _observations_from_response(response)

    if status == "no_data":
        return {"classification": "no_data", "observation_ids": ()}

    unique_observations = []
    seen_event_ids = set()
    for observation in observations:
        if observation.event_id in seen_event_ids:
            continue
        seen_event_ids.add(observation.event_id)
        if (
            observation.event_id != initial_observation.event_id
            and observation.source_id != initial_observation.source_id
        ):
            unique_observations.append(observation)

    compatible = [
        observation
        for observation in unique_observations
        if are_observations_compatible(
            initial_observation,
            observation,
            max_distance,
            max_time_difference,
        )
    ]
    if compatible:
        return {
            "classification": "compatible",
            "observation_ids": tuple(observation.event_id for observation in compatible),
        }

    return {
        "classification": "inconclusive",
        "observation_ids": tuple(observation.event_id for observation in unique_observations),
    }


def aggregate_verification_responses(
    initial_observation: Observation,
    responses,
    conversation_id: str,
    request_message_id: str,
    max_distance: float,
    max_time_difference: float,
) -> dict[str, object]:
    """Aggregate several responses for one verification request.

    Responses are accepted only when they are ``VERIFY_RESPONSE`` messages in
    the expected conversation and refer to the expected request. A message is
    processed once by ``message_id`` and an observation is counted once by
    ``event_id``. Source diversity is derived from the observations themselves,
    never from the transport sender or the response ``source_id``.

    The result contains ``classification``, unique independent
    ``observation_ids``, distinct observation ``source_ids`` and
    ``compatible_source_count``. Multiple observations from one source count
    as one compatible source.
    """
    _validate_observation(initial_observation, "initial_observation")
    _validate_reference(conversation_id, "conversation_id")
    _validate_reference(request_message_id, "request_message_id")
    _validate_limit(max_distance, "max_distance")
    _validate_limit(max_time_difference, "max_time_difference")

    seen_message_ids = set()
    unique_observations = {}
    compatible_ids = set()
    saw_observation_response = False
    saw_no_data = False

    for response in responses:
        if not isinstance(response, Message):
            raise TypeError("Each response must be a Message.")
        observations, status = _observations_from_response(response)
        if response.conversation_id != conversation_id:
            raise ValueError("VERIFY_RESPONSE belongs to another conversation.")
        if response.payload["request_message_id"] != request_message_id:
            raise ValueError("VERIFY_RESPONSE refers to another request.")
        if response.message_id in seen_message_ids:
            continue
        seen_message_ids.add(response.message_id)

        result = classify_verification_response(
            initial_observation,
            response,
            max_distance,
            max_time_difference,
        )
        if status == "no_data":
            saw_no_data = True
            continue
        saw_observation_response = True

        for observation in observations:
            if (
                observation.event_id == initial_observation.event_id
                or observation.source_id == initial_observation.source_id
                or observation.event_id in unique_observations
            ):
                continue
            unique_observations[observation.event_id] = observation

        compatible_ids.update(result["observation_ids"])

    compatible_ids.intersection_update(unique_observations)
    source_ids = {
        observation.source_id for observation in unique_observations.values()
    }
    compatible_source_ids = {
        unique_observations[event_id].source_id for event_id in compatible_ids
    }

    if compatible_ids:
        classification = "compatible"
    elif saw_observation_response:
        classification = "inconclusive"
    elif saw_no_data or not seen_message_ids:
        classification = "no_data"
    else:  # Defensive fallback for future response statuses.
        classification = "inconclusive"

    return {
        "classification": classification,
        "observation_ids": tuple(sorted(unique_observations)),
        "source_ids": tuple(sorted(source_ids)),
        "compatible_source_count": len(compatible_source_ids),
    }


def _observations_from_response(response: Message) -> tuple[tuple[Observation, ...], str]:
    if not isinstance(response, Message):
        raise TypeError("response must be a Message.")
    if response.message_type is not MessageType.VERIFY_RESPONSE:
        raise ValueError("response must be a VERIFY_RESPONSE message.")

    payload = response.payload
    if not isinstance(payload, dict):
        raise ValueError("VERIFY_RESPONSE payload must be an object.")
    request_message_id = payload.get("request_message_id")
    if not isinstance(request_message_id, str) or not request_message_id.strip():
        raise ValueError("VERIFY_RESPONSE must identify its request message.")

    status = payload.get("status")
    if status not in {"observations_available", "no_data"}:
        raise ValueError("VERIFY_RESPONSE status is invalid.")
    raw_observations = payload.get("observations")
    if not isinstance(raw_observations, list):
        raise ValueError("VERIFY_RESPONSE observations must be a list.")
    if status == "no_data" and raw_observations:
        raise ValueError("A no_data response cannot contain observations.")
    if status == "observations_available" and not raw_observations:
        raise ValueError("An observations_available response must contain observations.")

    observations = []
    for raw_observation in raw_observations:
        try:
            observations.append(model_from_dict(raw_observation, Observation))
        except (TypeError, ValueError, KeyError) as error:
            raise ValueError("VERIFY_RESPONSE contains an invalid observation.") from error
    return tuple(observations), status


def _validate_reference(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")


def _validate_observation(observation: Observation, name: str) -> None:
    if not isinstance(observation, Observation):
        raise TypeError(f"{name} must be an Observation.")


def _validate_limit(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite non-negative number.")
    if not isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite non-negative number.")

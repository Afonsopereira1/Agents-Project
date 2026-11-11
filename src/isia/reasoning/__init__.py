"""Regras de raciocínio sobre observações e ocorrências."""

from .corroboration import (
    aggregate_verification_responses,
    are_observations_compatible,
    classify_verification_response,
    decide_preliminary_verification,
    evaluate_preliminary_corroboration,
    select_eligible_sources,
)
from .allocation import MissionRegistry

__all__ = [
    "aggregate_verification_responses",
    "are_observations_compatible",
    "classify_verification_response",
    "decide_preliminary_verification",
    "evaluate_preliminary_corroboration",
    "select_eligible_sources",
    "MissionRegistry",
]

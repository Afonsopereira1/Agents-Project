"""Regras de raciocínio sobre observações e ocorrências."""

from .corroboration import (
    aggregate_verification_responses,
    are_observations_compatible,
    classify_verification_response,
    select_eligible_sources,
)

__all__ = [
    "aggregate_verification_responses",
    "are_observations_compatible",
    "classify_verification_response",
    "select_eligible_sources",
]

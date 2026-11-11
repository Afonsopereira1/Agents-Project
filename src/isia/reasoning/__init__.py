"""Regras de raciocínio sobre observações e ocorrências."""

from .corroboration import (
    are_observations_compatible,
    classify_verification_response,
    select_eligible_sources,
)

__all__ = [
    "are_observations_compatible",
    "classify_verification_response",
    "select_eligible_sources",
]

"""Regras de raciocínio sobre observações e ocorrências."""

from .corroboration import (
    aggregate_verification_responses,
    are_observations_compatible,
    classify_verification_response,
    decide_preliminary_verification,
    evaluate_preliminary_corroboration,
    select_eligible_sources,
)
from .allocation import (
    LocalResourceReservation,
    MissionRegistry,
    ReservationResult,
    ReservationStatus,
    accept_matches_proposal,
    build_accept_message,
    build_cfp_message,
    build_proposal_rejection_message,
    build_reservation_status_message,
    evaluate_cfp,
    reservation_status_matches_accept,
    select_best_proposal,
)

__all__ = [
    "aggregate_verification_responses",
    "are_observations_compatible",
    "classify_verification_response",
    "decide_preliminary_verification",
    "evaluate_preliminary_corroboration",
    "select_eligible_sources",
    "MissionRegistry",
    "LocalResourceReservation",
    "ReservationResult",
    "ReservationStatus",
    "accept_matches_proposal",
    "build_accept_message",
    "build_cfp_message",
    "build_proposal_rejection_message",
    "build_reservation_status_message",
    "evaluate_cfp",
    "reservation_status_matches_accept",
    "select_best_proposal",
]

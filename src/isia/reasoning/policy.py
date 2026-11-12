"""Regras operacionais de resposta; os limiares não são probabilidades."""

from dataclasses import asdict, dataclass

from isia.domain.models import Observation
from isia.domain.validation import is_finite_number
from isia.reasoning.allocation import RANGER_DECISION
from isia.reasoning.reputation import EvaluationResult


@dataclass(frozen=True)
class ResponsePolicy:
    patrol_threshold: float = 0.25
    ranger_threshold: float = 0.65
    severe_threshold: float = 0.8
    severe_patrol_threshold: float = 0.08
    ranger_min_groups: int = 2
    ranger_min_modalities: int = 2

    def __post_init__(self):
        for name in ("patrol_threshold", "ranger_threshold", "severe_threshold", "severe_patrol_threshold"):
            value = getattr(self, name)
            if not is_finite_number(value) or not 0 < value <= 1:
                raise ValueError(f"{name} deve estar em ]0, 1].")
        if not self.severe_patrol_threshold <= self.patrol_threshold <= self.ranger_threshold:
            raise ValueError("Os limiares devem respeitar severe_patrol <= patrol <= ranger.")
        for name in ("ranger_min_groups", "ranger_min_modalities"):
            value = getattr(self, name)
            if type(value) is not int or value < 2:
                raise ValueError(f"{name} deve ser um inteiro >= 2.")


def decide_response(
    evaluation: dict,
    policy: ResponsePolicy,
    *,
    severity: float,
    initial_observation: Observation,
    incident_id: str,
    mission_result: EvaluationResult | None = None,
) -> dict:
    """Escolher observar, verificar, pedir rangers ou encerrar.

    Só uma missão independente e fundamentada pode encerrar por refutação.
    A verdade de referência nunca entra na decisão operacional. ``severity``
    é gravidade configurada para a hipótese, não intensidade medida do sinal.
    """
    if not isinstance(policy, ResponsePolicy) or not isinstance(initial_observation, Observation):
        raise TypeError("São necessários ResponsePolicy e Observation.")
    if not isinstance(incident_id, str) or not incident_id.strip():
        raise ValueError("incident_id deve identificar a ocorrência.")
    score = evaluation["suspicion_score"]
    for value in (score, severity):
        if not is_finite_number(value) or not 0 <= value <= 1:
            raise ValueError("Score e gravidade devem estar entre 0 e 1.")
    group_count = evaluation["supporting_group_count"]
    if type(group_count) is not int or group_count < 0:
        raise ValueError("supporting_group_count deve ser inteiro não negativo.")
    modalities = evaluation["modalities"]
    if not isinstance(modalities, (tuple, list)) or any(not isinstance(m, str) for m in modalities):
        raise ValueError("modalities deve conter nomes de modalidades.")
    if type(evaluation["conflicting_evidence"]) is not bool:
        raise ValueError("conflicting_evidence deve ser booleano.")
    mission_rejection = None
    if mission_result is not None:
        if not isinstance(mission_result, EvaluationResult):
            raise TypeError("mission_result deve ser EvaluationResult.")
        if mission_result.basis != "independent_mission":
            raise ValueError("A política só aceita resultados operacionais de missão.")
        mission_rejection = mission_result.rejection_reason(initial_observation, incident_id)
        evidence_sources = {factor["source_id"] for factor in evaluation.get("factors", ())}
        if evidence_sources & set(mission_result.evidence_source_ids):
            mission_rejection = "non_independent_reference"

    patrol_threshold = (policy.severe_patrol_threshold if severity >= policy.severe_threshold
                        else policy.patrol_threshold)
    if mission_result is not None and mission_rejection is None:
        action = "close" if mission_result.outcome == "refuted" else RANGER_DECISION
        reason = f"independent_mission_{mission_result.outcome}"
    elif (score >= policy.ranger_threshold
          and group_count >= policy.ranger_min_groups
          and len(set(modalities) - {"unknown"}) >= policy.ranger_min_modalities
          and not evaluation["conflicting_evidence"]):
        action, reason = RANGER_DECISION, "diverse_reliable_evidence"
    elif score >= patrol_threshold:
        action = "request_mobile_verification"
        reason = "severe_event_requires_verification" if severity >= policy.severe_threshold else "patrol_threshold_reached"
    else:
        action, reason = "observe", "insufficient_evidence"
    return {
        **evaluation, "incident_id": incident_id, "decision": action, "reason": reason,
        "severity": severity, "policy": asdict(policy), "effective_patrol_threshold": patrol_threshold,
        "mission_result": asdict(mission_result) if mission_result else None,
        "mission_rejection": mission_rejection,
    }

"""Fiabilidade de alertas de ameaça, atualizada apenas pela camada de avaliação."""

from dataclasses import asdict, dataclass

from isia.domain.models import Observation, Position
from isia.domain.validation import is_finite_number


@dataclass(frozen=True)
class EvaluationResult:
    """Adjudicação explícita; não é uma votação nem uma mensagem MISSION_RESULT.

    O avaliador associa as observações ao incidente e verifica a proveniência.
    ``refuted`` exige exclusão fundamentada da ameaça no local/intervalo das
    observações; uma patrulha que não encontrou nada não basta.
    """

    result_id: str
    incident_id: str
    observation_ids: tuple[str, ...]
    outcome: str
    basis: str
    evaluated_at: float
    evidence_ids: tuple[str, ...] = ()
    evidence_source_ids: tuple[str, ...] = ()
    final: bool = False
    sufficient_coverage: bool = False

    def __post_init__(self):
        for value in (self.result_id, self.incident_id):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Resultado e incidente precisam de identificadores.")
        for values in (self.observation_ids, self.evidence_ids, self.evidence_source_ids):
            if not isinstance(values, tuple) or any(
                not isinstance(value, str) or not value.strip() for value in values
            ) or len(values) != len(set(values)):
                raise ValueError("Referências devem ser tuplos de IDs únicos.")
        if not self.observation_ids:
            raise ValueError("O resultado deve identificar observações avaliadas.")
        if self.outcome not in ("confirmed", "refuted", "inconclusive", "failed"):
            raise ValueError("Resultado de avaliação desconhecido.")
        if self.basis not in ("ground_truth", "independent_mission", "consensus"):
            raise ValueError("Fundamento de avaliação desconhecido.")
        if not is_finite_number(self.evaluated_at) or self.evaluated_at < 0:
            raise ValueError("evaluated_at deve ser finito e não negativo.")
        if type(self.final) is not bool or type(self.sufficient_coverage) is not bool:
            raise ValueError("final e sufficient_coverage devem ser booleanos.")

    def rejection_reason(self, observation: Observation, incident_id: str) -> str | None:
        if self.incident_id != incident_id or observation.event_id not in self.observation_ids:
            return "unrelated_result"
        if self.evaluated_at < observation.observed_at:
            return "result_precedes_observation"
        if not self.final or self.outcome not in ("confirmed", "refuted"):
            return "unresolved_result"
        if not self.sufficient_coverage or not self.evidence_ids:
            return "insufficient_reference"
        if self.basis == "consensus":
            return "agreement_is_not_reference"
        if set(self.evidence_ids) & set(self.observation_ids):
            return "circular_evidence"
        if self.basis == "independent_mission" and (
            not self.evidence_source_ids or observation.source_id in self.evidence_source_ids
        ):
            return "non_independent_reference"
        return None


class ReputationBook:
    """Uma atualização por fonte/incidente, com prior Beta e auditoria local.

    Mede utilidade do sinal como alerta de ameaça, não exatidão física do sensor.
    Um som real de trovão pode, portanto, ser um alerta de ameaça incorreto.
    ``run_id`` distingue amostras de execuções identificadas pelo avaliador;
    repetir o mesmo âmbito conserva a idempotência, sem presumir independência.
    """

    def __init__(self, alpha: float = 2.0, beta: float = 2.0):
        if any(not is_finite_number(value) or value <= 0 for value in (alpha, beta)):
            raise ValueError("alpha e beta devem ser finitos e positivos.")
        if not is_finite_number(alpha + beta):
            raise ValueError("A soma do prior deve ser finita.")
        self.alpha, self.beta = alpha, beta
        self._counts: dict[str, tuple[int, int]] = {}
        self._evaluated_events: set[tuple[str | None, str]] = set()
        self._evaluated_incidents: set[tuple[str | None, str, str]] = set()
        self.history: list[dict] = []

    def score(self, source_id: str) -> float:
        correct, incorrect = self._counts.get(source_id, (0, 0))
        return (correct + self.alpha) / (correct + incorrect + self.alpha + self.beta)

    def snapshot(self, source_ids) -> dict[str, float]:
        return {source_id: self.score(source_id) for source_id in sorted(set(source_ids))}

    def update(
        self, observation: Observation, incident_id: str, result: EvaluationResult,
        *, run_id: str | None = None,
    ) -> dict:
        if not isinstance(observation, Observation) or not isinstance(result, EvaluationResult):
            raise TypeError("São necessários Observation e EvaluationResult.")
        if run_id is not None and (not isinstance(run_id, str) or not run_id.strip()):
            raise ValueError("run_id deve identificar a execução de avaliação.")
        reason = result.rejection_reason(observation, incident_id)
        event_key = (run_id, observation.event_id)
        key = (run_id, observation.source_id, incident_id)
        if reason is None and (
            event_key in self._evaluated_events or key in self._evaluated_incidents
        ):
            reason = "already_evaluated"
        before = self.score(observation.source_id)
        if reason is None:
            correct, incorrect = self._counts.get(observation.source_id, (0, 0))
            self._counts[observation.source_id] = (
                correct + (result.outcome == "confirmed"),
                incorrect + (result.outcome == "refuted"),
            )
            self._evaluated_events.add(event_key)
            self._evaluated_incidents.add(key)
        record = {
            "event_id": observation.event_id, "source_id": observation.source_id,
            "incident_id": incident_id, "run_id": run_id, "result": asdict(result),
            "updated": reason is None, "reason": reason or "grounded_result",
            "before": before, "after": self.score(observation.source_id),
            "counts": self._counts.get(observation.source_id, (0, 0)),
            "alpha": self.alpha, "beta": self.beta,
        }
        self.history.append(record)
        return record


def result_from_ground_truth(
    observation: Observation, incident_id: str, ground_truth: dict,
    *, evaluated_at: float, run_id: str,
) -> EvaluationResult:
    """Adaptador exclusivo do avaliador para ``Scenario.ground_truth``.

    Exige atribuição explícita ao evento terminado. Falta de atribuição não
    significa falso positivo. O snapshot nunca é entregue ao SensorAgent.
    """
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id deve identificar a execução.")
    event_id = ground_truth["observations"].get(observation.event_id)
    matches = [event for event in ground_truth["events"] if event["event_id"] == event_id]
    if len(matches) > 1:
        raise ValueError("Evento de referência duplicado.")
    event = matches[0] if matches else None
    resolved = event is not None and event["state"] == "ended"
    if resolved and type(event["is_threat"]) is not bool:
        raise ValueError("is_threat deve ser booleano.")
    outcome = ("confirmed" if event["is_threat"] else "refuted") if resolved else "inconclusive"
    return EvaluationResult(
        result_id=f"{run_id}:evaluation:{observation.event_id}",
        incident_id=incident_id, observation_ids=(observation.event_id,),
        outcome=outcome, basis="ground_truth", evaluated_at=evaluated_at,
        evidence_ids=(f"{run_id}:ground_truth:{event_id}",) if resolved else (),
        final=resolved, sufficient_coverage=resolved,
    )


def result_from_mission(
    result, observation: Observation, incident_id: str,
    *, max_distance: float, max_delay_seconds: float,
) -> EvaluationResult:
    """Adjudicação automática de um ``MISSION_RESULT`` já validado pelo sensor.

    Só ``verify_incident`` confirmado é final. ``not_confirmed`` não exclui a
    ameaça e fica ``inconclusive``. Há cobertura quando a célula inspecionada
    e o instante da inspeção estão dentro dos limites experimentais dados.
    """
    for value in (max_distance, max_delay_seconds):
        if not is_finite_number(value) or value < 0:
            raise ValueError("Limites de cobertura devem ser finitos e não negativos.")
    payload = result.payload
    try:
        position = Position(**payload["position"])
        gap = abs(position.x - observation.position.x) + abs(position.y - observation.position.y)
        delay = payload["completed_at"] - observation.observed_at
        covered = (payload.get("task") == "verify_incident"
                   and gap <= max_distance and 0 <= delay <= max_delay_seconds)
    except (KeyError, TypeError, ValueError):
        covered = False  # Posição inválida/ausente não comprova cobertura.
    confirmed = payload.get("outcome") == "confirmed" and payload.get("task") == "verify_incident"
    return EvaluationResult(
        result_id=f"{result.message_id}:evaluation:{observation.event_id}",
        incident_id=incident_id, observation_ids=(observation.event_id,),
        outcome="confirmed" if confirmed else "inconclusive", basis="independent_mission",
        evaluated_at=result.created_at, evidence_ids=(result.message_id,),
        evidence_source_ids=(result.source_id,), final=confirmed, sufficient_coverage=covered,
    )

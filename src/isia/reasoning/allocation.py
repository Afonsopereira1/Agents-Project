"""Ponte local entre a decisão de corroboração e uma missão de verificação.

Este módulo ainda não negocia nem reserva recursos. Apenas materializa, de
forma idempotente, a missão que poderá ser usada por uma futura ronda de
Contract Net.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isfinite
from uuid import uuid4

from isia.communication.messages import (
    Message,
    MessageType,
    model_from_dict,
    model_to_dict,
)
from isia.domain.models import (
    Bid,
    Incident,
    Mission,
    Position,
    ResourceState,
    ResourceStatus,
)


MOBILE_VERIFICATION_DECISION = "request_mobile_verification"
MOBILE_VERIFICATION_TASK = "verify_incident"
MOBILE_VERIFICATION_CAPABILITY = "mobile_verification"
CONTRACT_NET_REJECT_REASON = "cfp_rejected"


@dataclass(frozen=True)
class ProposalSelection:
    """Resultado determinístico da avaliação de uma ronda de propostas."""

    winner: Message | None
    winner_bid: Bid | None
    winner_cost: float | None
    valid_proposals: tuple[Message, ...]
    reason: str


def _validate_simulated_time(value: object, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or value < 0
    ):
        raise ValueError(
            f"{name} deve ser um número finito e não negativo em segundos simulados."
        )
    return float(value)


def build_cfp_message(
    mission: Mission,
    created_at: float,
    deadline: float,
    *,
    message_id: str | None = None,
    conversation_id: str | None = None,
) -> Message:
    """Construir um ``CFP`` para uma missão existente.

    ``created_at`` e ``deadline`` são instantes absolutos em segundos de tempo
    simulado, usando a mesma referência temporal do relógio da simulação. O
    prazo tem de ser igual ou posterior à emissão. IDs omitidos são gerados
    localmente; IDs fornecidos pelo iniciador são mantidos para correlacionar
    futuras ``PROPOSAL``/respostas com este CFP.
    """
    if not isinstance(mission, Mission):
        raise TypeError("mission deve ser Mission.")

    created_at_value = _validate_simulated_time(created_at, "created_at")
    deadline_value = _validate_simulated_time(deadline, "deadline")
    if deadline_value < created_at_value:
        raise ValueError("deadline não pode ser anterior a created_at.")

    mission_data = model_to_dict(mission)
    payload = {
        field: mission_data[field]
        for field in ("task", "target", "required_capability", "priority")
    }
    payload["deadline"] = deadline_value

    return Message(
        message_id if message_id is not None else f"message-{uuid4()}",
        MessageType.CFP,
        created_at_value,
        payload,
        incident_id=mission.incident_id,
        mission_id=mission.mission_id,
        conversation_id=(
            conversation_id
            if conversation_id is not None
            else f"conversation-{uuid4()}"
        ),
    )


def _build_contract_net_response(
    cfp: Message,
    message_type: MessageType,
    created_at: float,
    resource_id: str,
    payload: dict[str, object],
) -> Message:
    return Message(
        f"{message_type.value.lower()}-{resource_id}-{cfp.message_id}",
        message_type,
        created_at,
        payload,
        incident_id=cfp.incident_id,
        mission_id=cfp.mission_id,
        source_id=resource_id,
        conversation_id=cfp.conversation_id,
    )


def evaluate_cfp(
    cfp: Message,
    resource: ResourceState,
    capabilities: Iterable[str],
    *,
    current_time: float,
    minimum_autonomy_percent: float,
    eta_seconds: float,
    energy_cost_percent: float,
    load: float,
) -> Message:
    """Avaliar localmente um CFP e devolver ``PROPOSAL`` ou ``REJECT``.

    ``current_time`` e ``eta_seconds`` usam segundos simulados. ``energy_cost``
    usa pontos percentuais de autonomia e ``load`` é uma fração entre 0 e 1.
    Estes três valores são parâmetros/configuração do cenário, não uma
    simulação física inventada por este módulo.

    A avaliação só usa o CFP, o estado local e as capacidades configuradas do
    recurso. Uma proposta não reserva o recurso nem altera qualquer estado.
    """
    if not isinstance(cfp, Message):
        raise TypeError("cfp deve ser Message.")
    if cfp.message_type is not MessageType.CFP:
        raise ValueError("A mensagem deve ser um CFP.")
    if not isinstance(resource, ResourceState):
        raise TypeError("resource deve ser ResourceState.")

    now = _validate_simulated_time(current_time, "current_time")
    minimum = _validate_simulated_time(
        minimum_autonomy_percent, "minimum_autonomy_percent"
    )
    if minimum > 100:
        raise ValueError("minimum_autonomy_percent não pode exceder 100.")

    try:
        configured_capabilities = frozenset(capabilities)
    except TypeError as error:
        raise TypeError("capabilities deve ser iterável.") from error
    if any(
        not isinstance(capability, str) or not capability.strip()
        for capability in configured_capabilities
    ):
        raise ValueError("As capacidades devem ser strings não vazias.")

    deadline = cfp.payload["deadline"]
    if now > deadline:
        return _build_contract_net_response(
            cfp,
            MessageType.REJECT,
            now,
            resource.resource_id,
            {"cfp_message_id": cfp.message_id, "reason": "cfp_expired"},
        )

    reason = None
    if resource.status is not ResourceStatus.AVAILABLE or not resource.available:
        reason = "resource_unavailable"
    elif cfp.payload["required_capability"] not in configured_capabilities:
        reason = "capability_mismatch"
    elif resource.autonomy_percent is None:
        reason = "autonomy_unknown"
    else:
        energy = _validate_simulated_time(energy_cost_percent, "energy_cost_percent")
        if resource.autonomy_percent - energy < minimum:
            reason = "autonomy_insufficient"

    if reason is not None:
        return _build_contract_net_response(
            cfp,
            MessageType.REJECT,
            now,
            resource.resource_id,
            {"cfp_message_id": cfp.message_id, "reason": reason},
        )

    bid = Bid(
        mission_id=cfp.mission_id,
        resource_id=resource.resource_id,
        eta=eta_seconds,
        energy_cost=energy,
        load=load,
    )
    return _build_contract_net_response(
        cfp,
        MessageType.PROPOSAL,
        now,
        resource.resource_id,
        {"cfp_message_id": cfp.message_id, "bid": model_to_dict(bid)},
    )


def _validate_cost_parameter(value: object, name: str, *, positive: bool) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or (value <= 0 if positive else value < 0)
    ):
        qualifier = "positivo" if positive else "não negativo"
        raise ValueError(f"{name} deve ser um número finito {qualifier}.")
    return float(value)


def _proposal_cost(
    bid: Bid,
    *,
    eta_weight: float,
    energy_weight: float,
    load_weight: float,
    eta_scale_seconds: float,
    energy_scale_percent: float,
    load_scale: float,
) -> float:
    """Normalizar as três dimensões antes de aplicar os pesos."""
    return (
        eta_weight * (bid.eta / eta_scale_seconds)
        + energy_weight * (bid.energy_cost / energy_scale_percent)
        + load_weight * (bid.load / load_scale)
    )


def select_best_proposal(
    cfp: Message,
    responses: Iterable[Message],
    *,
    eta_weight: float = 1.0,
    energy_weight: float = 1.0,
    load_weight: float = 1.0,
    eta_scale_seconds: float = 60.0,
    energy_scale_percent: float = 100.0,
    load_scale: float = 1.0,
) -> ProposalSelection:
    """Selecionar a melhor proposta válida de uma ronda Contract Net.

    O custo é determinístico e adimensional:

    ``w_eta * ETA/eta_scale + w_energy * energia/energy_scale +
    w_load * carga/load_scale``.

    ETA usa segundos simulados, energia usa pontos percentuais de autonomia e
    carga é uma fração entre 0 e 1. As escalas e pesos são parâmetros de
    engenharia; não representam uma calibração física. Empates são resolvidos
    por ``resource_id`` e depois por ``message_id``.

    Respostas inválidas, ``REJECT``, duplicados e propostas emitidas depois do
    ``deadline`` simulado do CFP são ignorados. Quando nenhuma proposta passa
    os filtros, ``winner`` e ``winner_bid`` são ``None`` e ``reason`` é
    ``"no_valid_proposals"``.
    """
    if not isinstance(cfp, Message):
        raise TypeError("cfp deve ser Message.")
    if cfp.message_type is not MessageType.CFP:
        raise ValueError("A mensagem deve ser um CFP.")

    weights = tuple(
        _validate_cost_parameter(value, name, positive=False)
        for name, value in (
            ("eta_weight", eta_weight),
            ("energy_weight", energy_weight),
            ("load_weight", load_weight),
        )
    )
    if not any(weight > 0 for weight in weights):
        raise ValueError("Pelo menos um peso deve ser positivo.")
    eta_scale = _validate_cost_parameter(
        eta_scale_seconds, "eta_scale_seconds", positive=True
    )
    energy_scale = _validate_cost_parameter(
        energy_scale_percent, "energy_scale_percent", positive=True
    )
    load_scale_value = _validate_cost_parameter(load_scale, "load_scale", positive=True)

    deadline = cfp.payload["deadline"]
    valid_by_resource: dict[str, tuple[float, str, Message, Bid]] = {}
    seen_message_ids: set[str] = set()
    for response in responses:
        if not isinstance(response, Message):
            continue
        if response.message_id in seen_message_ids:
            continue
        seen_message_ids.add(response.message_id)
        if response.message_type is not MessageType.PROPOSAL:
            continue
        if (
            response.mission_id != cfp.mission_id
            or response.incident_id != cfp.incident_id
            or response.conversation_id != cfp.conversation_id
            or response.created_at < cfp.created_at
            or response.created_at > deadline
            or response.payload.get("cfp_message_id") != cfp.message_id
            or not isinstance(response.source_id, str)
        ):
            continue
        raw_bid = response.payload.get("bid")
        if not isinstance(raw_bid, dict):
            continue
        try:
            bid = model_from_dict(raw_bid, Bid)
        except (TypeError, ValueError):
            continue
        if bid.mission_id != cfp.mission_id or bid.resource_id != response.source_id:
            continue

        cost = _proposal_cost(
            bid,
            eta_weight=weights[0],
            energy_weight=weights[1],
            load_weight=weights[2],
            eta_scale_seconds=eta_scale,
            energy_scale_percent=energy_scale,
            load_scale=load_scale_value,
        )
        candidate = (cost, bid.resource_id, response, bid)
        current = valid_by_resource.get(bid.resource_id)
        if current is None or (cost, response.message_id) < (
            current[0],
            current[2].message_id,
        ):
            valid_by_resource[bid.resource_id] = candidate

    ordered = tuple(
        candidate[2]
        for candidate in sorted(
            valid_by_resource.values(),
            key=lambda candidate: (candidate[0], candidate[1], candidate[2].message_id),
        )
    )
    if not ordered:
        return ProposalSelection(None, None, None, (), "no_valid_proposals")

    winner = ordered[0]
    winner_bid = model_from_dict(winner.payload["bid"], Bid)
    winner_cost = _proposal_cost(
        winner_bid,
        eta_weight=weights[0],
        energy_weight=weights[1],
        load_weight=weights[2],
        eta_scale_seconds=eta_scale,
        energy_scale_percent=energy_scale,
        load_scale=load_scale_value,
    )
    return ProposalSelection(
        winner,
        winner_bid,
        winner_cost,
        ordered,
        "proposal_selected",
    )


class MissionRegistry:
    """Registo local de missões criadas por um iniciador de ocorrência.

    A chave da decisão é a ocorrência e o tipo de decisão. Assim, repetir a
    mesma decisão do ``SensorAgent`` devolve a missão já criada em vez de
    criar uma segunda missão para o mesmo incidente.
    """

    def __init__(self) -> None:
        self._missions: dict[tuple[str, str], Mission] = {}

    def create_from_decision(
        self,
        incident: Incident,
        decision: Mapping[str, object],
        *,
        mission_id: str | None = None,
        priority: int = 0,
        target: Position | None = None,
    ) -> Mission | None:
        """Criar a missão móvel correspondente à decisão, se aplicável.

        ``None`` representa uma decisão que não pede verificação móvel. Para
        manter a ponte mínima, o destino default é a posição da primeira
        observação do incidente, usada como âncora determinística da
        ocorrência. O chamador pode fornecer um ``target`` explícito.
        """
        if not isinstance(incident, Incident):
            raise TypeError("incident deve ser Incident.")
        if not isinstance(decision, Mapping):
            raise TypeError("decision deve ser um mapping.")

        if decision.get("decision") != MOBILE_VERIFICATION_DECISION:
            return None

        key = (incident.incident_id, MOBILE_VERIFICATION_DECISION)
        existing = self._missions.get(key)
        if existing is not None:
            return existing

        mission = Mission(
            mission_id=mission_id or f"mission-{incident.incident_id}-mobile-verification",
            incident_id=incident.incident_id,
            task=MOBILE_VERIFICATION_TASK,
            target=target or incident.observations[0].position,
            required_capability=MOBILE_VERIFICATION_CAPABILITY,
            priority=priority,
        )
        self._missions[key] = mission
        return mission


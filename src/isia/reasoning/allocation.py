"""Raciocínio local para criação, negociação e reserva de missões."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isfinite
from threading import Lock
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


def _validate_contract_net_message(message: Message, message_type: MessageType) -> None:
    if not isinstance(message, Message):
        raise TypeError("message deve ser Message.")
    if message.message_type is not message_type:
        raise ValueError(f"A mensagem deve ser {message_type.value}.")
    for name in ("mission_id", "incident_id", "conversation_id"):
        if not isinstance(getattr(message, name), str) or not getattr(message, name).strip():
            raise ValueError(f"{name} deve estar presente.")


def build_accept_message(
    cfp: Message,
    proposal: Message,
    created_at: float,
    *,
    message_id: str | None = None,
    source_id: str | None = None,
) -> Message:
    """Construir ACCEPT correlacionado com um CFP e uma PROPOSAL.

    ``created_at`` é um instante absoluto em segundos simulados. A mensagem
    referencia explicitamente os IDs do CFP e da proposta, permitindo ao
    recurso rejeitar ACCEPTs de outra ronda sem reservar nada.
    """
    _validate_contract_net_message(cfp, MessageType.CFP)
    _validate_contract_net_message(proposal, MessageType.PROPOSAL)
    if (proposal.mission_id, proposal.incident_id, proposal.conversation_id) != (
        cfp.mission_id,
        cfp.incident_id,
        cfp.conversation_id,
    ):
        raise ValueError("A proposta não pertence ao CFP.")
    if proposal.payload.get("cfp_message_id") != cfp.message_id:
        raise ValueError("A proposta não referencia o CFP.")
    bid = model_from_dict(proposal.payload.get("bid"), Bid)
    if bid.mission_id != cfp.mission_id or bid.resource_id != proposal.source_id:
        raise ValueError("A proposta contém uma Bid incoerente.")
    created = _validate_simulated_time(created_at, "created_at")
    return Message(
        message_id or f"accept-{uuid4()}",
        MessageType.ACCEPT,
        created,
        {
            "cfp_message_id": cfp.message_id,
            "proposal_message_id": proposal.message_id,
            "resource_id": bid.resource_id,
        },
        incident_id=cfp.incident_id,
        mission_id=cfp.mission_id,
        source_id=source_id,
        conversation_id=cfp.conversation_id,
    )


def build_proposal_rejection_message(
    cfp: Message,
    proposal: Message,
    created_at: float,
    *,
    message_id: str | None = None,
) -> Message:
    """Construir REJECT do iniciador para uma proposta não selecionada."""
    accept = build_accept_message(
        cfp, proposal, created_at, message_id=message_id or f"reject-{uuid4()}"
    )
    return Message(
        accept.message_id,
        MessageType.REJECT,
        accept.created_at,
        {**accept.payload, "reason": "proposal_not_selected"},
        incident_id=accept.incident_id,
        mission_id=accept.mission_id,
        source_id=accept.source_id,
        conversation_id=accept.conversation_id,
    )


def accept_matches_proposal(
    accept: Message,
    cfp: Message,
    proposal: Message,
    resource_id: str,
) -> bool:
    """Validar todos os identificadores de uma aceitação para um recurso."""
    try:
        _validate_contract_net_message(accept, MessageType.ACCEPT)
        _validate_contract_net_message(cfp, MessageType.CFP)
        _validate_contract_net_message(proposal, MessageType.PROPOSAL)
        bid = model_from_dict(proposal.payload.get("bid"), Bid)
    except (TypeError, ValueError):
        return False
    return (
        accept.mission_id == cfp.mission_id == proposal.mission_id == bid.mission_id
        and accept.incident_id == cfp.incident_id == proposal.incident_id
        and accept.conversation_id == cfp.conversation_id == proposal.conversation_id
        and accept.payload.get("cfp_message_id") == cfp.message_id
        and accept.payload.get("proposal_message_id") == proposal.message_id
        and accept.payload.get("resource_id") == resource_id == proposal.source_id == bid.resource_id
    )


def build_reservation_status_message(
    accept: Message,
    result: ReservationResult,
    *,
    resource_id: str,
    created_at: float,
) -> Message:
    """Construir STATUS ``reserved`` ou falha, sem esconder a reserva."""
    _validate_contract_net_message(accept, MessageType.ACCEPT)
    if not isinstance(result, ReservationResult):
        raise TypeError("result deve ser ReservationResult.")
    if not isinstance(resource_id, str) or not resource_id.strip():
        raise ValueError("resource_id inválido.")
    status = "reserved" if result.confirmed else "reservation_failed"
    payload = {
        "accept_message_id": accept.message_id,
        "mission_id": accept.mission_id,
        "resource_id": resource_id,
        "status": status,
        "reservation_status": result.status,
    }
    if not result.confirmed:
        payload["reason"] = result.reason
    return Message(
        f"status-{resource_id}-{accept.message_id}",
        MessageType.STATUS,
        _validate_simulated_time(created_at, "created_at"),
        payload,
        incident_id=accept.incident_id,
        mission_id=accept.mission_id,
        source_id=resource_id,
        conversation_id=accept.conversation_id,
    )


def reservation_status_matches_accept(
    status: Message,
    accept: Message,
    resource_id: str,
) -> bool:
    """Validar confirmação STATUS recebida do recurso vencedor."""
    try:
        _validate_contract_net_message(status, MessageType.STATUS)
        _validate_contract_net_message(accept, MessageType.ACCEPT)
    except (TypeError, ValueError):
        return False
    return (
        status.mission_id == accept.mission_id
        and status.incident_id == accept.incident_id
        and status.conversation_id == accept.conversation_id
        and status.source_id == resource_id
        and status.payload.get("accept_message_id") == accept.message_id
        and status.payload.get("resource_id") == resource_id
        and status.payload.get("status") in ("reserved", "reservation_failed")
    )


class ReservationStatus:
    """Resultados públicos da tentativa de reserva local."""

    RESERVED = "reserved"
    ALREADY_RESERVED = "already_reserved"
    RESOURCE_OCCUPIED = "resource_occupied"
    INVALID_REQUEST = "invalid_request"


@dataclass(frozen=True)
class ReservationResult:
    """Resultado explícito de uma tentativa de reserva."""

    status: str
    resource_state: ResourceState
    mission_id: str | None
    reason: str

    @property
    def confirmed(self) -> bool:
        return self.status in (
            ReservationStatus.RESERVED,
            ReservationStatus.ALREADY_RESERVED,
        )


class LocalResourceReservation:
    """Reserva atómica e local de um único recurso móvel.

    O ``ResourceState`` continua a ser imutável; cada transição substitui a
    instância por outra devolvida por ``change_status``. O lock cobre também a
    associação do ``mission_id``, impedindo que duas threads observem
    simultaneamente o mesmo recurso como disponível.
    """

    def __init__(self, resource_state: ResourceState):
        if not isinstance(resource_state, ResourceState):
            raise TypeError("resource_state deve ser ResourceState.")
        self._resource_state = resource_state
        self._reserved_mission_id: str | None = None
        self._lock = Lock()

    @property
    def resource_state(self) -> ResourceState:
        with self._lock:
            return self._resource_state

    @property
    def reserved_mission_id(self) -> str | None:
        with self._lock:
            return self._reserved_mission_id

    def reserve(
        self,
        mission_id: object,
        *,
        resource_id: object | None = None,
    ) -> ReservationResult:
        """Tentar reservar este recurso para ``mission_id``.

        Pedidos inválidos devolvem ``INVALID_REQUEST`` em vez de alterar o
        estado. Uma repetição para a missão já associada é idempotente e
        devolve ``ALREADY_RESERVED``. Nenhuma destas respostas implementa
        ainda ACCEPT por XMPP ou uma reserva distribuída.
        """
        if not isinstance(mission_id, str) or not mission_id.strip():
            return self._result(
                ReservationStatus.INVALID_REQUEST,
                None,
                "mission_id_invalid",
            )
        if resource_id is not None and (
            not isinstance(resource_id, str)
            or not resource_id.strip()
            or resource_id != self._resource_state.resource_id
        ):
            return self._result(
                ReservationStatus.INVALID_REQUEST,
                mission_id,
                "resource_id_invalid",
            )

        with self._lock:
            if self._resource_state.status is ResourceStatus.RESERVED:
                if self._reserved_mission_id == mission_id:
                    return self._result_locked(
                        ReservationStatus.ALREADY_RESERVED,
                        mission_id,
                        "reservation_is_idempotent",
                    )
                return self._result_locked(
                    ReservationStatus.RESOURCE_OCCUPIED,
                    mission_id,
                    "resource_reserved_for_another_mission",
                )

            if (
                self._resource_state.status is not ResourceStatus.AVAILABLE
                or not self._resource_state.available
            ):
                return self._result_locked(
                    ReservationStatus.RESOURCE_OCCUPIED,
                    mission_id,
                    "resource_not_available",
                )

            self._resource_state = self._resource_state.change_status(
                ResourceStatus.RESERVED
            )
            self._reserved_mission_id = mission_id
            return self._result_locked(
                ReservationStatus.RESERVED,
                mission_id,
                "reservation_confirmed",
            )

    def _result(
        self,
        status: str,
        mission_id: str | None,
        reason: str,
    ) -> ReservationResult:
        with self._lock:
            return self._result_locked(status, mission_id, reason)

    def _result_locked(
        self,
        status: str,
        mission_id: str | None,
        reason: str,
    ) -> ReservationResult:
        return ReservationResult(
            status,
            self._resource_state,
            self._reserved_mission_id if status != ReservationStatus.INVALID_REQUEST else mission_id,
            reason,
        )


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


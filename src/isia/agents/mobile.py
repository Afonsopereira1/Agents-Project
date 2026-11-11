"""Agente móvel mínimo para a ronda inicial de Contract Net."""

from __future__ import annotations

import logging

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.template import Template

from isia.communication.messages import Message, MessageType
from isia.communication.transport import (
    CONTRACT_NET_PROTOCOL,
    ONTOLOGY,
    PERFORMATIVE_CFP,
    PERFORMATIVE_ACCEPT_PROPOSAL,
    PERFORMATIVE_INFORM,
    PERFORMATIVE_PROPOSE,
    PERFORMATIVE_REJECT_PROPOSAL,
    build_spade_message,
    parse_spade_message,
)
from isia.domain.models import ResourceState
from isia.reasoning.allocation import (
    LocalResourceReservation,
    ReservationResult,
    ReservationStatus,
    accept_matches_proposal,
    build_reservation_status_message,
    evaluate_cfp,
)

logger = logging.getLogger(__name__)


def _bare_jid(value: object) -> str:
    return str(value).split("/", 1)[0].lower()


class MobileResourceAgent(Agent):
    """Recurso móvel reutilizável por drones, veículos ou outros agentes.

    ETA, custo energético e carga são parâmetros do cenário. O relógio é
    sempre simulado e deve ser atualizado pelo chamador através de
    ``set_simulated_time``.
    """

    def __init__(
        self,
        jid: str,
        password: str,
        resource: ResourceState,
        capabilities,
        *,
        minimum_autonomy_percent: float,
        eta_seconds: float,
        energy_cost_percent: float,
        load: float,
        simulated_time: float = 0.0,
    ):
        super().__init__(jid, password)
        self.resource = resource
        self.capabilities = tuple(capabilities)
        self.minimum_autonomy_percent = minimum_autonomy_percent
        self.eta_seconds = eta_seconds
        self.energy_cost_percent = energy_cost_percent
        self.load = load
        self.simulated_time = simulated_time
        self.reservation = LocalResourceReservation(resource)
        self._proposal_context: dict[str, tuple[Message, Message, str]] = {}

    def set_simulated_time(self, simulated_time: float) -> None:
        self.simulated_time = simulated_time

    class ContractNetBehaviour(CyclicBehaviour):
        async def run(self):
            incoming = await self.receive(timeout=10)
            if incoming is None:
                return
            try:
                cfp = parse_spade_message(
                    incoming,
                    expected_protocol=CONTRACT_NET_PROTOCOL,
                )
                if cfp.message_type is not MessageType.CFP:
                    return
                agent: MobileResourceAgent = self.agent  # type: ignore[assignment]
                response = evaluate_cfp(
                    cfp,
                    agent.reservation.resource_state,
                    agent.capabilities,
                    current_time=agent.simulated_time,
                    minimum_autonomy_percent=agent.minimum_autonomy_percent,
                    eta_seconds=agent.eta_seconds,
                    energy_cost_percent=agent.energy_cost_percent,
                    load=agent.load,
                )
                if response.message_type is MessageType.PROPOSAL:
                    performative = PERFORMATIVE_PROPOSE
                else:
                    performative = PERFORMATIVE_REJECT_PROPOSAL
                reply = build_spade_message(
                    str(incoming.sender),
                    response,
                    performative=performative,
                    conversation_id=cfp.conversation_id,
                    in_reply_to=cfp.message_id,
                    protocol=CONTRACT_NET_PROTOCOL,
                )
                if response.message_type is MessageType.PROPOSAL:
                    proposal_context = (
                        cfp,
                        response,
                        str(incoming.sender),
                    )
                    agent._proposal_context[response.message_id] = proposal_context
                else:
                    proposal_context = None
                try:
                    await self.send(reply)
                except Exception as error:
                    if response.message_type is MessageType.PROPOSAL:
                        if agent._proposal_context.get(response.message_id) == proposal_context:
                            agent._proposal_context.pop(response.message_id, None)
                    logger.warning("Resposta Contract Net não enviada: %s", error)
            except (TypeError, ValueError) as error:
                logger.warning("CFP rejeitado: %s", error)

    class AcceptBehaviour(CyclicBehaviour):
        async def run(self):
            incoming = await self.receive(timeout=10)
            if incoming is None:
                return
            agent: MobileResourceAgent = self.agent  # type: ignore[assignment]
            try:
                accept = parse_spade_message(
                    incoming,
                    expected_protocol=CONTRACT_NET_PROTOCOL,
                )
                if accept.message_type is not MessageType.ACCEPT:
                    return
                context = agent._proposal_context.get(
                    accept.payload.get("proposal_message_id")
                )
                if context is None:
                    result = ReservationResult(
                        ReservationStatus.INVALID_REQUEST,
                        agent.reservation.resource_state,
                        accept.mission_id,
                        "proposal_not_correlated",
                    )
                else:
                    cfp, proposal, initiator = context
                    valid_sender = _bare_jid(incoming.sender) == _bare_jid(initiator)
                    valid_recipient = _bare_jid(getattr(incoming, "to", "")) == _bare_jid(agent.jid)
                    valid_source = accept.source_id is None or _bare_jid(accept.source_id) == _bare_jid(initiator)
                    if not valid_sender or not valid_source or not accept_matches_proposal(
                        accept, cfp, proposal, agent.reservation.resource_state.resource_id
                    ) or not valid_recipient:
                        result = ReservationResult(
                            ReservationStatus.INVALID_REQUEST,
                            agent.reservation.resource_state,
                            accept.mission_id,
                            "accept_correlation_invalid",
                        )
                    else:
                        result = agent.reservation.reserve(
                            accept.mission_id,
                            resource_id=agent.reservation.resource_state.resource_id,
                        )
                        agent.resource = result.resource_state
                status = build_reservation_status_message(
                    accept,
                    result,
                    resource_id=agent.reservation.resource_state.resource_id,
                    created_at=agent.simulated_time,
                )
                reply = build_spade_message(
                    str(incoming.sender),
                    status,
                    performative=PERFORMATIVE_INFORM,
                    conversation_id=accept.conversation_id,
                    in_reply_to=accept.message_id,
                    protocol=CONTRACT_NET_PROTOCOL,
                )
                await self.send(reply)
            except (TypeError, ValueError) as error:
                logger.warning("ACCEPT rejeitado: %s", error)

    async def setup(self):
        template = Template(
            metadata={
                "performative": PERFORMATIVE_CFP,
                "ontology": ONTOLOGY,
                "protocol": CONTRACT_NET_PROTOCOL,
            }
        )
        self.add_behaviour(self.ContractNetBehaviour(), template)
        accept_template = Template(
            metadata={
                "performative": PERFORMATIVE_ACCEPT_PROPOSAL,
                "ontology": ONTOLOGY,
                "protocol": CONTRACT_NET_PROTOCOL,
            }
        )
        self.add_behaviour(self.AcceptBehaviour(), accept_template)

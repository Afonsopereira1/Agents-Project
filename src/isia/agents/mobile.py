"""Agente móvel mínimo para a ronda inicial de Contract Net."""

from __future__ import annotations

import logging

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.template import Template

from isia.communication.messages import MessageType
from isia.communication.transport import (
    CONTRACT_NET_PROTOCOL,
    ONTOLOGY,
    PERFORMATIVE_CFP,
    PERFORMATIVE_PROPOSE,
    PERFORMATIVE_REJECT_PROPOSAL,
    build_spade_message,
    parse_spade_message,
)
from isia.domain.models import ResourceState
from isia.reasoning.allocation import evaluate_cfp

logger = logging.getLogger(__name__)


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
                    agent.resource,
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
                await self.send(reply)
            except (TypeError, ValueError) as error:
                logger.warning("CFP rejeitado: %s", error)

    async def setup(self):
        template = Template(
            metadata={
                "performative": PERFORMATIVE_CFP,
                "ontology": ONTOLOGY,
                "protocol": CONTRACT_NET_PROTOCOL,
            }
        )
        self.add_behaviour(self.ContractNetBehaviour(), template)

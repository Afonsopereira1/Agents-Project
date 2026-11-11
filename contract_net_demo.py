"""Demonstração real de uma ronda CFP -> PROPOSAL/REJECT via SPADE/XMPP.

O prazo do CFP usa segundos simulados. O timeout de receção do iniciador usa
segundos reais e só limita quanto tempo a demonstração espera pelo XMPP.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import Mapping

import spade
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour
from spade.template import Template

from isia.agents.mobile import MobileResourceAgent
from isia.communication.messages import Message, MessageType
from isia.communication.transport import (
    CONTRACT_NET_PROTOCOL,
    ONTOLOGY,
    PERFORMATIVE_CFP,
    PERFORMATIVE_PROPOSE,
    PERFORMATIVE_REJECT_PROPOSAL,
    build_spade_message,
    parse_spade_message,
)
from isia.domain.models import Mission, Position, ResourceState
from isia.reasoning.allocation import build_cfp_message

logger = logging.getLogger(__name__)


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Defina a variável de ambiente {name}.")
    return value


def configurable_float(name: str, default: float, *, positive: bool = False) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError as error:
        raise SystemExit(f"A variável {name} deve ser numérica.") from error
    if parsed < 0 or (positive and parsed <= 0):
        raise SystemExit(f"A variável {name} deve ser válida e não negativa.")
    return parsed


def bare_jid(value: object) -> str:
    """Normalizar um JID SPADE para comparar remetentes sem o recurso."""
    return str(value).split("/", 1)[0].lower()


def response_matches_cfp(
    incoming,
    response: Message,
    cfp: Message,
    expected_resources: Mapping[str, str],
) -> bool:
    """Validar origem, tipo, IDs, payload e metadados de uma resposta."""
    sender = bare_jid(getattr(incoming, "sender", ""))
    resource_id = expected_resources.get(sender)
    if resource_id is None:
        return False
    if response.message_type not in (MessageType.PROPOSAL, MessageType.REJECT):
        return False
    expected_performative = (
        PERFORMATIVE_PROPOSE
        if response.message_type is MessageType.PROPOSAL
        else PERFORMATIVE_REJECT_PROPOSAL
    )
    return (
        response.mission_id == cfp.mission_id
        and response.incident_id == cfp.incident_id
        and response.conversation_id == cfp.conversation_id
        and response.source_id == resource_id
        and response.payload.get("cfp_message_id") == cfp.message_id
        and incoming.get_metadata("ontology") == ONTOLOGY
        and incoming.get_metadata("protocol") == CONTRACT_NET_PROTOCOL
        and incoming.get_metadata("performative") == expected_performative
        and incoming.get_metadata("conversation-id") == cfp.conversation_id
        and incoming.get_metadata("in-reply-to") == cfp.message_id
    )


class ContractNetInitiatorAgent(Agent):
    """Iniciador temporário que apenas envia um CFP e recolhe respostas."""

    def __init__(
        self,
        jid: str,
        password: str,
        mission: Mission,
        resource_jids: Mapping[str, str],
        *,
        simulated_time: float,
        deadline: float,
        receive_timeout: float,
    ):
        super().__init__(jid, password)
        self.mission = mission
        self.resource_jids = dict(resource_jids)
        self.simulated_time = simulated_time
        self.deadline = deadline
        self.receive_timeout = receive_timeout
        self.cfp: Message | None = None
        self.responses: dict[str, Message] = {}
        self.behaviour = None

    class ContractNetBehaviour(OneShotBehaviour):
        async def run(self):
            agent: ContractNetInitiatorAgent = self.agent  # type: ignore[assignment]
            agent.cfp = build_cfp_message(
                agent.mission,
                created_at=agent.simulated_time,
                deadline=agent.deadline,
            )
            cfp = agent.cfp
            expected_resources = {
                bare_jid(jid): resource_id
                for jid, resource_id in agent.resource_jids.items()
            }

            for recipient in agent.resource_jids:
                outgoing = build_spade_message(
                    recipient,
                    cfp,
                    performative=PERFORMATIVE_CFP,
                    conversation_id=cfp.conversation_id,
                    reply_with=cfp.message_id,
                    protocol=CONTRACT_NET_PROTOCOL,
                )
                await self.send(outgoing)
                logger.info(
                    "CFP enviado para %s: mission_id=%s incident_id=%s "
                    "conversation_id=%s deadline_simulado=%.3f",
                    recipient,
                    cfp.mission_id,
                    cfp.incident_id,
                    cfp.conversation_id,
                    agent.deadline,
                )

            received_message_ids: set[str] = set()
            started_at = time.monotonic()
            while len(agent.responses) < len(expected_resources):
                remaining = agent.receive_timeout - (time.monotonic() - started_at)
                if remaining <= 0:
                    break
                incoming = await self.receive(timeout=remaining)
                if incoming is None:
                    break
                try:
                    response = parse_spade_message(
                        incoming,
                        expected_protocol=CONTRACT_NET_PROTOCOL,
                    )
                except (TypeError, ValueError) as error:
                    logger.warning("Resposta Contract Net inválida ignorada: %s", error)
                    continue
                if response.message_id in received_message_ids:
                    logger.warning("Resposta duplicada ignorada: %s", response.message_id)
                    continue
                if not response_matches_cfp(
                    incoming, response, cfp, expected_resources
                ):
                    logger.warning("Resposta não correlacionada ignorada.")
                    continue

                sender = bare_jid(incoming.sender)
                if sender in agent.responses:
                    logger.warning("Resposta adicional do recurso ignorada: %s", sender)
                    continue
                received_message_ids.add(response.message_id)
                agent.responses[sender] = response
                if response.message_type is MessageType.REJECT:
                    logger.info(
                        "REJECT recebido de %s: motivo=%s",
                        sender,
                        response.payload.get("reason", "não indicado"),
                    )
                else:
                    logger.info("PROPOSAL recebido de %s: %s", sender, response.payload)

            missing = set(expected_resources) - set(agent.responses)
            if missing:
                logger.warning(
                    "Timeout real de %.3fs; sem resposta de: %s",
                    agent.receive_timeout,
                    sorted(missing),
                )

    async def setup(self):
        self.behaviour = self.ContractNetBehaviour()
        self.add_behaviour(
            self.behaviour,
            Template(metadata={"ontology": ONTOLOGY, "protocol": CONTRACT_NET_PROTOCOL}),
        )


def build_demo_mission() -> Mission:
    return Mission(
        "mission-contract-net-demo",
        "incident-contract-net-demo",
        "verify_incident",
        Position(6, 9),
        "mobile_verification",
        2,
    )


async def main():
    initiator_jid = os.environ.get("CONTRACT_INITIATOR_JID", "initiator@localhost")
    resource_one_jid = os.environ.get("CONTRACT_RESOURCE_ONE_JID", "drone@localhost")
    resource_two_jid = os.environ.get("CONTRACT_RESOURCE_TWO_JID", "vehicle@localhost")
    simulated_time = configurable_float("CONTRACT_SIMULATED_TIME", 20.0)
    deadline = configurable_float("CONTRACT_DEADLINE", simulated_time + 15.0)
    receive_timeout = configurable_float(
        "CONTRACT_RECEIVE_TIMEOUT_SECONDS", 10.0, positive=True
    )

    mission = build_demo_mission()
    resource_jids = {
        resource_one_jid: "drone-demo",
        resource_two_jid: "vehicle-demo",
    }
    eligible = MobileResourceAgent(
        resource_one_jid,
        required_env("CONTRACT_RESOURCE_ONE_PASSWORD"),
        ResourceState("drone-demo", "drone", Position(3, 4), True, 85.0),
        ("mobile_verification",),
        minimum_autonomy_percent=20.0,
        eta_seconds=4.0,
        energy_cost_percent=10.0,
        load=0.25,
        simulated_time=simulated_time,
    )
    unavailable = MobileResourceAgent(
        resource_two_jid,
        required_env("CONTRACT_RESOURCE_TWO_PASSWORD"),
        ResourceState("vehicle-demo", "vehicle", Position(8, 4), False, 80.0),
        ("mobile_verification",),
        minimum_autonomy_percent=20.0,
        eta_seconds=7.0,
        energy_cost_percent=15.0,
        load=0.5,
        simulated_time=simulated_time,
    )
    initiator = ContractNetInitiatorAgent(
        initiator_jid,
        required_env("CONTRACT_INITIATOR_PASSWORD"),
        mission,
        resource_jids,
        simulated_time=simulated_time,
        deadline=deadline,
        receive_timeout=receive_timeout,
    )

    started = []
    try:
        for agent in (eligible, unavailable, initiator):
            await agent.start(auto_register=True)
            started.append(agent)
        await initiator.behaviour.join()
        logger.info("Ronda terminada: %d resposta(s) válida(s).", len(initiator.responses))
    finally:
        for agent in reversed(started):
            try:
                await agent.stop()
            except Exception:  # pragma: no cover - segurança do encerramento real
                logger.exception("Erro ao encerrar agente.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    spade.run(main())

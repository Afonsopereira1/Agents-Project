"""Demonstração real de uma ronda CFP -> PROPOSAL/REJECT via SPADE/XMPP.

O prazo do CFP usa segundos simulados. O timeout de receção do iniciador usa
segundos reais e só limita quanto tempo a demonstração espera pelo XMPP.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Mapping
from math import isfinite

import spade
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour
from spade.template import Template

from isia.agents.mobile import MobileResourceAgent
from isia.communication.messages import Message, MessageType
from isia.communication.transport import (
    CONTRACT_NET_PROTOCOL,
    ONTOLOGY,
    PERFORMATIVE_ACCEPT_PROPOSAL,
    PERFORMATIVE_CFP,
    PERFORMATIVE_INFORM,
    PERFORMATIVE_PROPOSE,
    PERFORMATIVE_REJECT_PROPOSAL,
    build_spade_message,
    parse_spade_message,
)
from isia.domain.models import Mission, MissionStatus, Position, ResourceState
from isia.reasoning.allocation import (
    AllocationOutcome,
    ContractNetResult,
    build_accept_message,
    build_cfp_message,
    build_proposal_rejection_message,
    reservation_status_matches_accept,
    select_best_proposal,
)

logger = logging.getLogger(__name__)


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Defina a variável de ambiente {name}.")
    return value


def configurable_float(name: str, default: float, *, positive: bool = False) -> float:
    value = os.environ.get(name)
    try:
        parsed = float(default if value is None else value)
    except (TypeError, ValueError, OverflowError) as error:
        raise SystemExit(f"A variável {name} deve ser numérica.") from error
    if not isfinite(parsed) or parsed < 0 or (positive and parsed <= 0):
        constraint = "positiva" if positive else "não negativa"
        raise SystemExit(f"A variável {name} deve ser finita e {constraint}.")
    return parsed


def configurable_rounds(name: str, default: int = 2) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as error:
        raise SystemExit(f"A variável {name} deve ser um inteiro entre 1 e 2.") from error
    if not 1 <= parsed <= 2:
        raise SystemExit(f"A variável {name} deve ser um inteiro entre 1 e 2.")
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


def confirmation_matches_accept(
    incoming,
    status: Message,
    accept: Message,
    *,
    winner_jid: str,
    resource_id: str,
    initiator_jid: str,
) -> bool:
    """Validar a confirmação XMPP do recurso exatamente aceite."""
    return (
        bare_jid(getattr(incoming, "sender", "")) == bare_jid(winner_jid)
        and bare_jid(getattr(incoming, "to", "")) == bare_jid(initiator_jid)
        and reservation_status_matches_accept(status, accept, resource_id)
        and incoming.get_metadata("ontology") == ONTOLOGY
        and incoming.get_metadata("protocol") == CONTRACT_NET_PROTOCOL
        and incoming.get_metadata("performative") == PERFORMATIVE_INFORM
        and incoming.get_metadata("conversation-id") == accept.conversation_id
        and incoming.get_metadata("in-reply-to") == accept.message_id
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
        max_rounds: int = 2,
    ):
        super().__init__(jid, password)
        self.mission = mission
        self.resource_jids = dict(resource_jids)
        self.simulated_time = simulated_time
        self.deadline = deadline
        self.receive_timeout = receive_timeout
        if type(max_rounds) is not int or not 1 <= max_rounds <= 2:
            raise ValueError("max_rounds deve ser um inteiro entre 1 e 2.")
        self.max_rounds = max_rounds
        self.cfp: Message | None = None
        self.responses: dict[str, Message] = {}
        self.selection = None
        self.accept: Message | None = None
        self.confirmation: Message | None = None
        self.result: ContractNetResult | None = None
        self.round_history: list[Message] = []
        self.behaviour = None

    class ContractNetBehaviour(OneShotBehaviour):
        async def run(self):
            agent: ContractNetInitiatorAgent = self.agent  # type: ignore[assignment]
            expected_resources = {
                bare_jid(jid): resource_id
                for jid, resource_id in agent.resource_jids.items()
            }
            for round_number in range(1, agent.max_rounds + 1):
                agent.cfp = build_cfp_message(
                    agent.mission,
                    created_at=agent.simulated_time,
                    deadline=agent.deadline,
                    round_number=round_number,
                )
                cfp = agent.cfp
                agent.round_history.append(cfp)
                agent.responses = {}
                agent.selection = None
                received_message_ids: set[str] = set()

                for recipient in agent.resource_jids:
                    await self.send(build_spade_message(
                        recipient, cfp, performative=PERFORMATIVE_CFP,
                        conversation_id=cfp.conversation_id,
                        reply_with=cfp.message_id,
                        protocol=CONTRACT_NET_PROTOCOL,
                    ))
                    logger.info("Ronda %d: CFP enviado para %s (%s)", round_number, recipient, cfp.message_id)

                started_at = time.monotonic()
                while len(agent.responses) < len(expected_resources):
                    remaining = agent.receive_timeout - (time.monotonic() - started_at)
                    if remaining <= 0:
                        break
                    incoming = await self.receive(timeout=remaining)
                    if incoming is None:
                        break
                    try:
                        response = parse_spade_message(incoming, expected_protocol=CONTRACT_NET_PROTOCOL)
                    except (TypeError, ValueError):
                        continue
                    if response.message_id in received_message_ids or not response_matches_cfp(
                        incoming, response, cfp, expected_resources
                    ):
                        continue
                    sender = bare_jid(incoming.sender)
                    if sender in agent.responses:
                        continue
                    received_message_ids.add(response.message_id)
                    agent.responses[sender] = response
                    logger.info("Ronda %d: %s recebido de %s", round_number, response.message_type.value, sender)

                selection = select_best_proposal(cfp, agent.responses.values())
                agent.selection = selection
                if selection.winner is None:
                    agent.result = ContractNetResult(
                        AllocationOutcome.NO_ELIGIBLE_PROPOSALS, agent.mission,
                        round_number, "no_valid_proposals", selection=selection,
                    )
                    return

                winner = selection.winner
                winner_sender = next(sender for sender, response in agent.responses.items()
                                     if response.message_id == winner.message_id)
                decision_time = max(
                    agent.simulated_time,
                    *(proposal.created_at for proposal in selection.valid_proposals),
                )
                accept = build_accept_message(cfp, winner, decision_time,
                                              source_id=bare_jid(agent.jid))
                agent.accept = accept
                await self.send(build_spade_message(
                    winner_sender, accept, performative=PERFORMATIVE_ACCEPT_PROPOSAL,
                    conversation_id=accept.conversation_id, in_reply_to=winner.message_id,
                    reply_with=accept.message_id, protocol=CONTRACT_NET_PROTOCOL,
                ))

                for proposal in selection.valid_proposals:
                    if proposal.message_id == winner.message_id:
                        continue
                    sender = next(candidate for candidate, response in agent.responses.items()
                                  if response.message_id == proposal.message_id)
                    rejection = build_proposal_rejection_message(cfp, proposal, decision_time)
                    await self.send(build_spade_message(
                        sender, rejection, performative=PERFORMATIVE_REJECT_PROPOSAL,
                        conversation_id=rejection.conversation_id,
                        in_reply_to=proposal.message_id, protocol=CONTRACT_NET_PROTOCOL,
                    ))

                started_confirmation = time.monotonic()
                while True:
                    remaining = agent.receive_timeout - (time.monotonic() - started_confirmation)
                    if remaining <= 0:
                        agent.result = ContractNetResult(
                            AllocationOutcome.CONFIRMATION_UNKNOWN, agent.mission,
                            round_number, "confirmation_timeout", selection=selection,
                        )
                        return
                    incoming = await self.receive(timeout=remaining)
                    if incoming is None:
                        agent.result = ContractNetResult(
                            AllocationOutcome.CONFIRMATION_UNKNOWN, agent.mission,
                            round_number, "confirmation_timeout", selection=selection,
                        )
                        return
                    try:
                        status = parse_spade_message(incoming, expected_protocol=CONTRACT_NET_PROTOCOL)
                    except (TypeError, ValueError):
                        continue
                    if not confirmation_matches_accept(
                        incoming, status, accept, winner_jid=winner_sender,
                        resource_id=winner.source_id, initiator_jid=str(agent.jid),
                    ):
                        continue
                    agent.confirmation = status
                    if status.payload.get("status") == "reserved":
                        agent.mission = agent.mission.change_status(MissionStatus.RESERVED)
                        agent.result = ContractNetResult(
                            AllocationOutcome.RESERVATION_CONFIRMED, agent.mission,
                            round_number, "reservation_confirmed", selection=selection,
                            confirmation=status,
                        )
                        return
                    agent.result = ContractNetResult(
                        AllocationOutcome.RESERVATION_REJECTED, agent.mission,
                        round_number, status.payload.get("reason", "reservation_failed"),
                        selection=selection, confirmation=status,
                    )
                    if round_number == agent.max_rounds:
                        return
                    logger.info("Reserva recusada; iniciar nova ronda sem reutilizar o CFP.")
                    break

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
    max_rounds = configurable_rounds("CONTRACT_MAX_ROUNDS")

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
        max_rounds=max_rounds,
    )

    started = []
    try:
        for agent in (eligible, unavailable, initiator):
            await agent.start(auto_register=True)
            started.append(agent)
        await initiator.behaviour.join()
        logger.info(
            "Negociação terminada: resultado=%s rondas=%d respostas=%d",
            initiator.result.outcome if initiator.result else "unknown",
            initiator.result.rounds if initiator.result else 0,
            len(initiator.responses),
        )
        if initiator.selection is None or initiator.selection.winner is None:
            logger.info("Nenhuma proposta válida.")
        else:
            logger.info(
                "Melhor proposta: recurso=%s custo_normalizado=%.6f",
                initiator.selection.winner_bid.resource_id,
                initiator.selection.winner_cost,
            )
            logger.info("Estado final da missão: %s", initiator.mission.status.value)
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

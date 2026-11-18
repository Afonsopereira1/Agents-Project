"""Negociação, reserva e execução local de um recurso móvel."""

from __future__ import annotations

import logging
import asyncio
from time import monotonic

from isia.simulation.movement import MissionExecution, distance, nonnegative

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
    PERFORMATIVE_REFUSE,
    PERFORMATIVE_REJECT_PROPOSAL,
    bare_jid as _bare_jid,
    build_spade_message,
    parse_spade_message,
)
from isia.domain.models import Mission, Position, ResourceState, ResourceStatus
from isia.reasoning.allocation import (
    LocalResourceReservation,
    ReservationResult,
    ReservationStatus,
    _validate_simulated_time,
    accept_matches_proposal,
    build_reservation_status_message,
    evaluate_cfp,
)

logger = logging.getLogger(__name__)
# Prazo local para aceitar uma proposta após terminar a recolha do CFP.
# Não altera o deadline inclusivo para emissão de PROPOSAL.
PROPOSAL_ACCEPTANCE_WINDOW_SECONDS = 10.0
# Fila ordenada: um pedido que não é renovado em duas esperas do iniciador (2 x 5 s simulados) sai da lista.
WAITING_TTL_SECONDS = 10.0
# shortcut: com o relógio simulado parado só o tempo real retira um pedido; rever se o relógio passar a avançar sempre.
WAITING_TTL_REAL_SECONDS = 5.0


class MobileResourceAgent(Agent):
    """Recurso móvel reutilizável por drones, veículos ou outros agentes.

    Com configure_execution, ETA e energia vêm do percurso de ida e volta.
    Sem essa configuração, mantém a demonstração de reserva da Etapa 5.
    O relógio simulado é atualizado através de ``set_simulated_time``.
    """

    silent_invalid = False  # True: um ACCEPT que não bate com a proposta fica sem resposta
    ordered_queue = False  # True: com vários pedidos em espera, só o primeiro da fila recebe proposta
    chain_missions = False  # True: no regresso à base, com o resultado entregue, aceita a missão seguinte
    resend_replies = False  # True: a um CFP ou ACCEPT repetido responde outra vez com a mesma resposta

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
        simulated_time = _validate_simulated_time(simulated_time, "simulated_time")
        super().__init__(jid, password)
        self.resource = resource
        self.capabilities = tuple(capabilities)
        self.minimum_autonomy_percent = minimum_autonomy_percent
        self.eta_seconds = eta_seconds
        self.energy_cost_percent = energy_cost_percent
        self.load = load
        self.simulated_time = simulated_time
        self.reservation = LocalResourceReservation(resource)
        self.base = resource.position
        self._proposal_context: dict[str, tuple[Message, Message, str]] = {}
        self._closed_cfp_ids: set[str] = set()
        # (iniciador, missão) -> (-prioridade, espera desde, idem em tempo real, último pedido, idem em tempo real)
        self._waiting = {}
        self._latest_cfp_times: dict[tuple[str, str], float] = {}
        self._latest_cfp_rounds: dict[tuple[str, str], tuple[int, str]] = {}
        self._accepted_proposal_ids: set[str] = set()
        self.execution_options = None
        self.execution = None
        self.executions = []
        self._execution_context = None
        self._result_sent = False
        self._result_message = None
        self._completed_accepts = set()
        # Reenvio: respostas já dadas, para repetir sem reavaliar. CFP recusado e ACCEPT confirmado.
        self._refusals = {}
        self._accept_replies = {}

    def configure_execution(self, world, inspect, *, speed=1.0, energy_per_cell=1.0,
                            service_seconds=1.0):
        for name, value in (("speed", speed), ("energy_per_cell", energy_per_cell),
                            ("service_seconds", service_seconds)):
            nonnegative(value, name)
        if speed == 0 or not callable(inspect):
            raise ValueError("Velocidade positiva e inspetor são obrigatórios.")
        world.validate_position(self.resource.position)
        self.execution_options = dict(world=world, inspect=inspect, speed=speed,
                                      energy_per_cell=energy_per_cell, service_seconds=service_seconds,
                                      minimum_energy=self.minimum_autonomy_percent)

    def is_turn(self, requester, priority):
        """Fila ordenada: regista quem pede e diz se é a sua vez.

        Primeiro a ocorrência mais grave; em caso de empate, a que espera há mais tempo.
        """
        now, real = self.simulated_time, monotonic()
        self._waiting = {key: entry for key, entry in self._waiting.items()
                         if now - entry[3] <= WAITING_TTL_SECONDS and real - entry[4] <= WAITING_TTL_REAL_SECONDS}
        since = self._waiting.get(requester, (0, now, real))[1:3]
        self._waiting[requester] = (-priority, *since, now, real)
        # A ordem só usa o que não muda entre pedidos; o último pedido serve apenas para a validade.
        return min(self._waiting, key=lambda key: self._waiting[key][:3]) == requester

    def returning(self):
        """Encadear missões: a caminho da base e com o resultado entregue, o recurso já pode ser pedido."""
        execution = self.execution
        return (self.chain_missions and execution is not None and not execution.finished
                and self._result_sent and execution.resource.status is ResourceStatus.RETURNING)

    def _close_execution(self):
        accept, _ = self._execution_context
        proposal_id = accept.payload["proposal_message_id"]
        self._accepted_proposal_ids.discard(proposal_id)
        self._invalidate_proposal(proposal_id)

    def evaluate_request(self, cfp):
        eta, energy = self.eta_seconds, self.energy_cost_percent
        state = self.reservation.resource_state
        if self.returning():
            state = state.change_status(ResourceStatus.AVAILABLE)  # só para avaliar; a reserva não muda
        if self.execution_options is not None:
            target = Position(**cfp.payload["target"])
            if not self.execution_options["world"].contains(target):
                return Message(
                    f"reject-{cfp.message_id}-{self.resource.resource_id}", MessageType.REJECT,
                    self.simulated_time, {"cfp_message_id": cfp.message_id, "reason": "target_outside_map"},
                    mission_id=cfp.mission_id, incident_id=cfp.incident_id,
                    conversation_id=cfp.conversation_id, source_id=self.resource.resource_id)
            cells = distance(state.position, target)
            eta = cells / self.execution_options["speed"]
            # Ida a partir da posição atual e regresso à base; parado na base, é o dobro da ida.
            home = self.base if self.chain_missions else state.position
            energy = (cells + distance(target, home)) * self.execution_options["energy_per_cell"]
        response = evaluate_cfp(
            cfp, state, self.capabilities,
            current_time=self.simulated_time, minimum_autonomy_percent=self.minimum_autonomy_percent,
            eta_seconds=eta, energy_cost_percent=energy, load=self.load)
        if (response.payload.get("reason") == "resource_unavailable"
                and self.execution is not None and not self.execution.finished):
            # Ocupado numa missão: dizer quando fica livre, para o iniciador não perguntar de 5 em 5 s.
            response = Message(
                response.message_id, MessageType.REJECT, response.created_at,
                {**response.payload, "busy_until": self.execution.free_at(self.chain_missions)},
                mission_id=cfp.mission_id, incident_id=cfp.incident_id,
                conversation_id=cfp.conversation_id, source_id=self.resource.resource_id)
        return response

    def start_execution(self, cfp, accept, initiator):
        if self.execution_options is None or accept.message_id in self._completed_accepts:
            return
        if self.execution is not None and not self.execution.finished:
            return
        mission = Mission(cfp.mission_id, cfp.incident_id, cfp.payload["task"],
                          Position(**cfp.payload["target"]), cfp.payload["required_capability"],
                          cfp.payload["priority"])
        self.execution = MissionExecution(self.reservation, mission, now=self.simulated_time,
                                          home=self.base if self.chain_missions else None,
                                          **self.execution_options)
        self.executions.append(self.execution)
        self._execution_context = (accept, initiator)
        self._completed_accepts.add(accept.message_id)
        self._result_sent = False
        self._result_message = None

    class ExecutionBehaviour(CyclicBehaviour):
        async def run(self):
            agent = self.agent
            await asyncio.sleep(0.001)
            execution = agent.execution
            if execution is None:
                return
            execution.advance(agent.simulated_time)
            agent.resource = execution.resource
            if execution.finished:
                agent._close_execution()
            if execution.result is not None and not agent._result_sent:
                accept, initiator = agent._execution_context
                if agent._result_message is None:
                    agent._result_message = Message(
                        f"result-{accept.message_id}", MessageType.MISSION_RESULT,
                        agent.simulated_time,
                        {**execution.result, "accept_message_id": accept.message_id,
                         "resource_id": agent.resource.resource_id, "task": execution.mission.task},
                        incident_id=accept.incident_id, mission_id=accept.mission_id,
                        source_id=agent.resource.resource_id, conversation_id=accept.conversation_id)
                result = agent._result_message
                outgoing = build_spade_message(
                    initiator, result, performative=PERFORMATIVE_INFORM,
                    conversation_id=result.conversation_id, in_reply_to=accept.message_id,
                    protocol=CONTRACT_NET_PROTOCOL)
                try:
                    await self.send(outgoing)
                except Exception as error:
                    logger.warning("Resultado não enviado; o regresso continua: %s", error)
                    return
                agent._result_sent = True
                if accept.message_id in agent._accept_replies:
                    agent._accept_replies[accept.message_id].append(outgoing)

    def set_simulated_time(self, simulated_time: float) -> None:
        value = _validate_simulated_time(simulated_time, "simulated_time")
        if value < self.simulated_time:
            raise ValueError("O relógio do recurso não pode recuar.")
        self.simulated_time = value
        self._expire_proposals()

    def _invalidate_proposal(self, proposal_id: str) -> None:
        context = self._proposal_context.pop(proposal_id, None)
        if context is not None:
            self._closed_cfp_ids.add(context[0].message_id)

    def _expire_proposals(self) -> None:
        _validate_simulated_time(self.simulated_time, "simulated_time")
        for proposal_id, (cfp, _, _) in tuple(self._proposal_context.items()):
            if proposal_id in self._accepted_proposal_ids:
                continue  # Preservar confirmações idempotentes de reservas existentes.
            if (
                self.simulated_time - cfp.payload["deadline"]
                > PROPOSAL_ACCEPTANCE_WINDOW_SECONDS
            ):
                self._invalidate_proposal(proposal_id)

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
                agent._expire_proposals()
                initiator = _bare_jid(incoming.sender)
                negotiation = (initiator, cfp.mission_id)
                if (
                    cfp.message_id in agent._closed_cfp_ids
                    or cfp.created_at < agent._latest_cfp_times.get(negotiation, -1)
                ):
                    refusal = agent._refusals.get((initiator, cfp.message_id))
                    if refusal is not None:
                        await self.send(refusal)  # a recusa perdeu-se: repetir a mesma, sem reavaliar
                    return
                existing = next((
                    context for context in agent._proposal_context.values()
                    if context[0].message_id == cfp.message_id
                    and _bare_jid(context[2]) == initiator
                ), None)
                if existing is not None and existing[0].to_dict() != cfp.to_dict():
                    logger.warning("CFP repetido com conteúdo divergente: %s", cfp.message_id)
                    return
                round_number = cfp.payload.get("round_number")
                latest_round = agent._latest_cfp_rounds.get(negotiation)
                if round_number is not None and latest_round is not None:
                    latest_number, latest_cfp_id = latest_round
                    if round_number < latest_number or (
                        round_number == latest_number and cfp.message_id != latest_cfp_id
                    ):
                        return
                response = existing[1] if existing is not None else agent.evaluate_request(cfp)
                if agent.ordered_queue and existing is None and (
                        response.message_type is MessageType.PROPOSAL
                        or response.payload.get("reason") == "resource_unavailable"):
                    # Ocupado ou livre, o pedido entra na fila; livre, só o primeiro recebe proposta.
                    if not agent.is_turn(negotiation, cfp.payload["priority"]) and (
                            response.message_type is MessageType.PROPOSAL):
                        response = Message(
                            f"reject-{cfp.message_id}-{agent.resource.resource_id}", MessageType.REJECT,
                            agent.simulated_time, {"cfp_message_id": cfp.message_id, "reason": "waiting_turn"},
                            mission_id=cfp.mission_id, incident_id=cfp.incident_id,
                            conversation_id=cfp.conversation_id, source_id=agent.resource.resource_id)
                agent._latest_cfp_times[negotiation] = cfp.created_at
                if round_number is not None:
                    agent._latest_cfp_rounds[negotiation] = (round_number, cfp.message_id)
                for proposal_id, (previous_cfp, _, previous_sender) in tuple(agent._proposal_context.items()):
                    previous_round = previous_cfp.payload.get("round_number")
                    # Sem ordinais comparáveis, um empate temporal não prova
                    # sucessão: conservar os contextos legados separadamente.
                    newer_round = (
                        round_number > previous_round
                        if round_number is not None and previous_round is not None
                        else cfp.created_at > previous_cfp.created_at
                    )
                    if (
                        previous_cfp.mission_id == cfp.mission_id
                        and _bare_jid(previous_sender) == initiator
                        and previous_cfp.message_id != cfp.message_id
                        and newer_round
                        and proposal_id not in agent._accepted_proposal_ids
                    ):
                        agent._invalidate_proposal(proposal_id)
                if response.message_type is MessageType.PROPOSAL:
                    performative = PERFORMATIVE_PROPOSE
                else:
                    performative = PERFORMATIVE_REFUSE
                reply = build_spade_message(
                    str(incoming.sender),
                    response,
                    performative=performative,
                    conversation_id=cfp.conversation_id,
                    in_reply_to=cfp.message_id,
                    protocol=CONTRACT_NET_PROTOCOL,
                )
                if response.message_type is MessageType.PROPOSAL:
                    proposal_context = existing or (
                        cfp,
                        response,
                        str(incoming.sender),
                    )
                    agent._proposal_context[response.message_id] = proposal_context
                else:
                    proposal_context = None
                    agent._closed_cfp_ids.add(cfp.message_id)
                    if agent.resend_replies:
                        agent._refusals[(initiator, cfp.message_id)] = reply
                try:
                    await self.send(reply)
                except Exception as error:
                    if response.message_type is MessageType.PROPOSAL and existing is None:
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
                expected_performative = {
                    MessageType.ACCEPT: PERFORMATIVE_ACCEPT_PROPOSAL,
                    MessageType.REJECT: PERFORMATIVE_REJECT_PROPOSAL,
                }.get(accept.message_type)
                if expected_performative is None or (
                    incoming.get_metadata("performative") != expected_performative
                ):
                    logger.warning("Decisão Contract Net rejeitada: intenção e corpo incoerentes")
                    return
                agent._expire_proposals()
                context = agent._proposal_context.get(
                    accept.payload.get("proposal_message_id")
                )
                if accept.message_type is MessageType.REJECT:
                    if context is not None:
                        cfp, proposal, initiator = context
                        if (
                            _bare_jid(incoming.sender) == _bare_jid(initiator)
                            and _bare_jid(getattr(incoming, "to", "")) == _bare_jid(agent.jid)
                            and (accept.source_id is None or _bare_jid(accept.source_id) == _bare_jid(initiator))
                            and incoming.get_metadata("in-reply-to") == proposal.message_id
                            and accept.mission_id == cfp.mission_id
                            and accept.incident_id == cfp.incident_id
                            and accept.conversation_id == cfp.conversation_id
                            and accept.payload.get("cfp_message_id") == cfp.message_id
                            and accept.payload.get("resource_id") == proposal.source_id
                            and proposal.created_at <= accept.created_at <= agent.simulated_time
                            and proposal.message_id not in agent._accepted_proposal_ids
                        ):
                            agent._invalidate_proposal(proposal.message_id)
                            agent._waiting.pop((_bare_jid(initiator), cfp.mission_id), None)
                    return
                if accept.message_id in agent._completed_accepts:
                    # Uma missão terminada nunca volta a reservar por replay; com reenvio, repete
                    # a confirmação e o resultado já enviados ao iniciador original.
                    for stored in tuple(agent._accept_replies.get(accept.message_id, ())):
                        await self.send(stored)
                    return
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
                    ) or not valid_recipient or (
                        incoming.get_metadata("in-reply-to") != proposal.message_id
                        or accept.created_at > agent.simulated_time
                    ):
                        if agent.silent_invalid:
                            # Contra-amplificação: responder daria tráfego grátis a quem envia lixo.
                            logger.warning("ACCEPT incoerente ignorado: %s", accept.message_id)
                            return
                        result = ReservationResult(
                            ReservationStatus.INVALID_REQUEST,
                            agent.reservation.resource_state,
                            accept.mission_id,
                            "accept_correlation_invalid",
                        )
                    elif (agent.ordered_queue and proposal.message_id not in agent._accepted_proposal_ids
                          and not agent.is_turn((_bare_jid(initiator), cfp.mission_id), cfp.payload["priority"])):
                        # Entre a proposta e o ACCEPT pediu alguém mais grave: a reserva fica para esse.
                        result = ReservationResult(
                            ReservationStatus.RESOURCE_OCCUPIED, agent.reservation.resource_state,
                            accept.mission_id, "waiting_turn")
                    else:
                        if agent.returning():
                            # Encadear: o regresso acaba aqui e a missão seguinte parte da posição atual.
                            agent.execution.advance(agent.simulated_time)
                            agent.execution.release()
                            agent._close_execution()
                        result = agent.reservation.reserve(
                            accept.mission_id,
                            resource_id=agent.reservation.resource_state.resource_id,
                        )
                        agent.resource = result.resource_state
                        if result.confirmed:
                            agent._accepted_proposal_ids.add(proposal.message_id)
                            agent._waiting.pop((_bare_jid(initiator), cfp.mission_id), None)
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
                if agent.resend_replies and result.confirmed and context is not None:
                    agent._accept_replies[accept.message_id] = [reply]
                try:
                    await self.send(reply)
                except Exception as error:
                    logger.warning("Confirmação não enviada: %s", error)
                finally:
                    if result.confirmed and context is not None:
                        agent.start_execution(cfp, accept, initiator)
            except (TypeError, ValueError) as error:
                logger.warning("ACCEPT rejeitado: %s", error)

    async def setup(self):
        if self.execution_options is not None:
            self.add_behaviour(self.ExecutionBehaviour(), Template(metadata={"protocol": "mission-clock"}))
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
        reject_template = Template(
            metadata={
                "performative": PERFORMATIVE_REJECT_PROPOSAL,
                "ontology": ONTOLOGY,
                "protocol": CONTRACT_NET_PROTOCOL,
            }
        )
        self.add_behaviour(self.AcceptBehaviour(), accept_template | reject_template)

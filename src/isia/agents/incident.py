"""Ciclo local de um incidente iniciado pelo próprio sensor, sem despachante."""

from dataclasses import replace
import logging
from time import monotonic

from spade.template import Template

from isia.agents.sensor import SensorAgent
from isia.communication.messages import Message, MessageType, model_from_dict
from isia.communication.transport import (
    ONTOLOGY, CONTRACT_NET_PROTOCOL, build_spade_message, parse_spade_message,
)
from isia.domain.incident_state import IncidentState, IncidentStatus
from isia.domain.models import Bid, Incident, Mission, MissionStatus
from isia.reasoning.allocation import (
    MissionRegistry, build_cfp_message, build_accept_message,
    build_proposal_rejection_message, select_best_proposal,
    reservation_status_matches_accept, RANGER_TASK, RANGER_CAPABILITY,
)
from isia.reasoning.policy import ResponsePolicy, decide_response
from isia.reasoning.reputation import EvaluationResult


logger = logging.getLogger(__name__)


def bare(value):
    return str(value).split("/", 1)[0].lower()


class IncidentSensorAgent(SensorAgent):
    """O sensor corrobora, negoceia, recebe resultados e encerra a ocorrência."""

    def configure_mvp(self, patrols, rangers, *, receive_timeout=2.0, max_attempts=2,
                      selection_weights=None):
        if type(max_attempts) is not int or max_attempts < 1:
            raise ValueError("max_attempts deve ser positivo.")
        from isia.simulation.movement import nonnegative
        nonnegative(receive_timeout, "receive_timeout")
        if receive_timeout == 0:
            raise ValueError("receive_timeout deve ser positivo.")
        self.patrols, self.rangers = dict(patrols), dict(rangers)
        self.receive_timeout, self.max_attempts = receive_timeout, max_attempts
        self.selection_weights = dict(selection_weights or {})
        self.simulated_time = self.created_at or 0.0
        self.incident_state = None
        self.timeline = []
        self.results = []
        self.missions = []
        self.incident_observations = ()
        self.cycle_done = False
        self.close_reason = None

    def record(self, event, **details):
        self.timeline.append({"time": self.simulated_time, "event": event, **details})

    def transition(self, status):
        self.incident_state = self.incident_state.change_status(status)
        self.record(status.value)

    class IncidentBehaviour(SensorAgent.VerificationBehaviour):
        def validated_close_decision(self, initial_observation, incident_id):
            """Revalidar o fundamento antes de executar a ação de encerramento."""
            agent = self.agent
            decision = agent.decision
            try:
                if not isinstance(agent.response_policy, ResponsePolicy):
                    raise ValueError("O encerramento exige uma política configurada.")
                reference = EvaluationResult(**decision["mission_result"])
                checked = decide_response(
                    decision, agent.response_policy, severity=agent.severity,
                    initial_observation=initial_observation, incident_id=incident_id,
                    mission_result=reference,
                )
                if checked["decision"] == "close":
                    return checked
            except (KeyError, TypeError, ValueError):
                pass
            return {**decision, "decision": "observe", "reason": "unsubstantiated_close"}

        def result_matches_assignment(self, incoming, result, assignment, mission):
            """A mesma validação aplica-se a resultados normais e antecipados."""
            jid, accept, resource_id = assignment
            return (result is not None and result.message_type is MessageType.MISSION_RESULT
                    and bare(incoming.sender) == jid and bare(incoming.to) == bare(self.agent.jid)
                    and incoming.get_metadata("performative") == "inform"
                    and incoming.get_metadata("in-reply-to") == accept.message_id
                    and result.mission_id == accept.mission_id
                    and result.incident_id == accept.incident_id
                    and result.conversation_id == accept.conversation_id
                    and result.source_id == resource_id
                    and result.payload.get("resource_id") == resource_id
                    and result.payload.get("accept_message_id") == accept.message_id
                    and result.payload["task"] == mission.task
                    and accept.created_at <= result.payload["completed_at"] <= result.created_at
                    and result.created_at <= self.agent.simulated_time)

        async def send_body(self, recipient, body, performative, reply_to=None):
            self.agent.record(body.message_type.value, recipient=recipient,
                              mission_id=body.mission_id, payload=body.payload)
            await self.send(build_spade_message(
                recipient, body, performative=performative,
                conversation_id=body.conversation_id, in_reply_to=reply_to,
                protocol=CONTRACT_NET_PROTOCOL))

        async def receive_until(self, deadline):
            remaining = deadline - monotonic()
            if remaining <= 0:
                return None
            incoming = await self.receive(timeout=remaining)
            if incoming is None or monotonic() >= deadline:
                return None
            try:
                body = parse_spade_message(incoming, expected_protocol=CONTRACT_NET_PROTOCOL)
            except (TypeError, ValueError):
                return (incoming, None)
            if body.created_at > self.agent.simulated_time:
                return (incoming, None)
            return incoming, body

        async def allocate(self, mission, candidates, attempt):
            agent = self.agent
            # Um único resultado, apenas durante a confirmação deste ACCEPT.
            self._pending_mission_result = None
            cfp = build_cfp_message(mission, agent.simulated_time,
                                    agent.simulated_time + 100, round_number=attempt)
            for jid in candidates:
                await self.send_body(jid, cfp, "cfp")
            responses = {}
            deadline = monotonic() + agent.receive_timeout
            while len(responses) < len(candidates):
                received = await self.receive_until(deadline)
                if received is None:
                    break
                incoming, body = received
                sender = bare(incoming.sender)
                if body is None or sender not in candidates or sender in responses:
                    continue
                if not (body.message_type in (MessageType.PROPOSAL, MessageType.REJECT)
                        and body.incident_id == cfp.incident_id and body.mission_id == cfp.mission_id
                        and body.conversation_id == cfp.conversation_id
                        and body.source_id == candidates[sender]
                        and body.payload.get("cfp_message_id") == cfp.message_id
                        and incoming.get_metadata("in-reply-to") == cfp.message_id
                        and incoming.get_metadata("performative") == (
                            "propose" if body.message_type is MessageType.PROPOSAL else "reject-proposal")
                        and cfp.created_at <= body.created_at <= cfp.payload["deadline"]):
                    continue
                if body.message_type is MessageType.PROPOSAL:
                    try:
                        bid = model_from_dict(body.payload.get("bid"), Bid)
                    except (TypeError, ValueError):
                        continue
                    if bid.mission_id != cfp.mission_id or bid.resource_id != candidates[sender]:
                        continue
                responses[sender] = body
            selection = select_best_proposal(cfp, responses.values(), **agent.selection_weights)
            winner = selection.winner
            if winner is None:
                return None, "no_eligible_proposals"
            winner_jid = next(jid for jid, body in responses.items() if body.message_id == winner.message_id)
            accept = build_accept_message(cfp, winner, agent.simulated_time, source_id=bare(agent.jid))
            await self.send_body(winner_jid, accept, "accept-proposal", winner.message_id)
            for jid, proposal in responses.items():
                if proposal.message_type is MessageType.PROPOSAL and jid != winner_jid:
                    rejection = build_proposal_rejection_message(cfp, proposal, agent.simulated_time)
                    try:
                        await self.send_body(jid, rejection, "reject-proposal", proposal.message_id)
                    except Exception as error:
                        logger.warning("REJECT não enviado a %s para a missão %s: %s",
                                       jid, mission.mission_id, error)
            assignment = (winner_jid, accept, winner.source_id)
            deadline = monotonic() + agent.receive_timeout
            confirmed = False
            try:
                while True:
                    received = await self.receive_until(deadline)
                    if received is None:
                        return None, "confirmation_unknown"
                    incoming, status = received
                    if self.result_matches_assignment(incoming, status, assignment, mission):
                        if self._pending_mission_result is None:
                            self._pending_mission_result = received
                        continue
                    if (status is not None and bare(incoming.sender) == winner_jid
                            and incoming.get_metadata("in-reply-to") == accept.message_id
                            and incoming.get_metadata("performative") == "inform"
                            and reservation_status_matches_accept(status, accept, winner.source_id)):
                        if status.payload["status"] != "reserved":
                            return None, "reservation_rejected"
                        confirmed = True
                        agent.record("reserved", resource_id=winner.source_id, mission_id=mission.mission_id)
                        return assignment, None
            finally:
                if not confirmed:
                    self._pending_mission_result = None

        async def mission_result(self, assignment, mission):
            agent = self.agent
            _, _, resource_id = assignment
            pending = getattr(self, "_pending_mission_result", None)
            self._pending_mission_result = None
            # O prazo real limita falhas de transporte; o movimento usa só tempo simulado.
            deadline = monotonic() + agent.receive_timeout * 10
            while True:
                received = pending if pending is not None else await self.receive_until(deadline)
                pending = None
                if received is None:
                    return None
                incoming, result = received
                if self.result_matches_assignment(incoming, result, assignment, mission):
                    agent.results.append(result)
                    agent.record("MISSION_RESULT", resource_id=resource_id, payload=result.payload)
                    return result

        async def execute_task(self, mission, candidates):
            agent = self.agent
            remaining = {bare(jid): resource for jid, resource in candidates.items()}
            for attempt in range(1, agent.max_attempts + 1):
                assignment, failure = await self.allocate(mission, remaining, attempt)
                if assignment is None:
                    agent.close_reason = failure
                    if failure == "reservation_rejected" and attempt < agent.max_attempts:
                        continue
                    return None
                agent.transition(IncidentStatus.RESPONDING)
                running = mission.change_status(MissionStatus.RESERVED).change_status(MissionStatus.RUNNING)
                result = await self.mission_result(assignment, mission)
                if result is None:
                    # Silêncio não prova falha nem permite atribuir outra missão.
                    agent.close_reason = "mission_result_unknown"
                    agent.transition(IncidentStatus.ALLOCATING)
                    return None
                outcome = result.payload["outcome"]
                agent.missions.append(running.change_status(
                    MissionStatus.FAILED if outcome == "failed" else MissionStatus.DONE))
                if outcome in ("confirmed", "not_confirmed"):
                    return result
                agent.transition(IncidentStatus.ALLOCATING)
                remaining.pop(assignment[0])
                agent.close_reason = outcome
                mission = replace(mission, mission_id=f"{mission.mission_id}-retry-{attempt}")
                if not remaining:
                    break
            return None

        async def run(self):
            agent = self.agent
            observations = tuple(agent.observation_feed.recent())
            if not observations:
                agent.close_reason, agent.cycle_done = "no_alert", True
                return
            initial = observations[0]
            incident_id = f"incident-{initial.event_id}"
            agent.incident_observations = observations
            agent.incident_state = IncidentState(incident_id)
            agent.record("ALERT", observation_id=initial.event_id)
            agent.transition(IncidentStatus.VERIFYING)
            await super().run()
            if agent.decision.get("decision") == "close":
                agent.decision = self.validated_close_decision(initial, incident_id)
            agent.record("corroboration", decision=agent.decision)
            agent.transition(IncidentStatus.ASSESSING)
            mission = MissionRegistry().create_from_decision(Incident(incident_id, observations), agent.decision)
            if agent.decision.get("decision") == "close":
                agent.close_reason = agent.decision["reason"]
                agent.transition(IncidentStatus.CLOSED)
            elif mission is None:
                agent.transition(IncidentStatus.WATCHING)
                # MVP de uma janela: sem nova evidência, termina como expirado.
                agent.transition(IncidentStatus.EXPIRED)
                agent.close_reason = "insufficient_corroboration"
            else:
                agent.transition(IncidentStatus.ALLOCATING)
                candidates = agent.rangers if mission.task == RANGER_TASK else agent.patrols
                result = await self.execute_task(mission, candidates)
                if (mission.task == "verify_incident" and result is not None
                        and result.payload["outcome"] == "confirmed"):
                    agent.transition(IncidentStatus.ALLOCATING)
                    response = Mission(f"{mission.mission_id}-response", incident_id,
                                       RANGER_TASK, mission.target, RANGER_CAPABILITY, mission.priority)
                    result = await self.execute_task(response, agent.rangers)
                if result is None:
                    agent.transition(IncidentStatus.UNRESOLVED)
                else:
                    agent.close_reason = result.payload["outcome"]
                    agent.transition(IncidentStatus.CLOSED)
            agent.record("INCIDENT_CLOSED", status=agent.incident_state.status.value,
                         reason=agent.close_reason)
            agent.cycle_done = True

    async def setup(self):
        self.behaviour = self.IncidentBehaviour()
        self.add_behaviour(self.behaviour, Template(metadata={"ontology": ONTOLOGY}))

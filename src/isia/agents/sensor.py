"""Agente sensor que inicia uma verificação e aguarda a resposta."""

from __future__ import annotations

import logging
import uuid
from time import monotonic
from typing import Any

from spade.agent import Agent
from spade.behaviour import OneShotBehaviour
from spade.template import Template

from isia.communication.messages import Message, MessageType, model_to_dict
from isia.communication.transport import (
    ONTOLOGY,
    PERFORMATIVE_INFORM,
    PERFORMATIVE_REQUEST,
    VERIFICATION_PROTOCOL,
    build_spade_message,
    parse_spade_message,
)
from isia.reasoning.corroboration import (
    aggregate_verification_responses,
    build_observation_hypothesis,
    decide_preliminary_verification,
    evaluate_preliminary_corroboration,
)
from isia.domain.models import Observation

logger = logging.getLogger(__name__)
RESPONSE_TIMEOUT_SECONDS = 10.0


def response_matches_request(
    incoming: Any,
    response: Message,
    request: Message,
    expected_sender: str,
) -> bool:
    """Valida a correlação e a origem de uma resposta de verificação."""
    sender = str(getattr(incoming, "sender", "")).split("/", 1)[0].lower()
    expected = expected_sender.split("/", 1)[0].lower()
    return (
        response.message_type is MessageType.VERIFY_RESPONSE
        and response.conversation_id == request.conversation_id
        and response.incident_id == request.incident_id
        and response.created_at >= request.created_at
        and incoming.get_metadata("conversation-id") == request.conversation_id
        and incoming.get_metadata("in-reply-to") == request.message_id
        and response.payload.get("request_message_id") == request.message_id
        and sender == expected
    )


class SensorAgent(Agent):
    """Agente sensor com dados de exemplo, sem dependência da Etapa 2."""

    def __init__(self, jid: str, password: str, informant_jid: str):
        super().__init__(jid, password)
        self.informant_jid = informant_jid
        self.observation_feed = None
        self.created_at: float | None = None
        self.response: Message | None = None
        self.conversation_id: str | None = None
        self.initial_observation = None
        self.aggregate_summary = None
        self.evaluation_summary = None
        self.decision = None
        self.eligible_source_ids: tuple[str, ...] = ()
        self.max_distance: float | None = None
        self.max_time_difference: float | None = None
        self.minimum_compatible_sources: int | None = None
        self.incompatibility_rules = None
        self.compatibility_rules = None
        # Histórico local, indexado pela conversa e pelo pedido. Não contém
        # credenciais, estado do simulador ou ground truth.
        self.verification_history: dict[str, dict[str, dict[str, object]]] = {}

    def set_local_observation_feed(self, observation_feed, created_at: float) -> None:
        """Give the agent only its local feed and simulation emission time."""
        self.observation_feed = observation_feed
        self.created_at = created_at

    def set_corroboration_context(
        self,
        eligible_source_ids,
        max_distance: float,
        max_time_difference: float,
        minimum_compatible_sources: int,
        incompatibility_rules=None,
        compatibility_rules=None,
    ) -> None:
        """Give the agent only the metadata and limits needed for evaluation."""
        self.eligible_source_ids = tuple(eligible_source_ids)
        self.max_distance = max_distance
        self.max_time_difference = max_time_difference
        self.minimum_compatible_sources = minimum_compatible_sources
        self.incompatibility_rules = incompatibility_rules
        self.compatibility_rules = compatibility_rules

    class VerificationBehaviour(OneShotBehaviour):
        async def run(self):
            agent: SensorAgent = self.agent  # type: ignore[assignment]
            conversation_id = f"conversation-{uuid.uuid4().hex}"
            agent.conversation_id = conversation_id

            observations = _recent_observations(agent.observation_feed)

            if observations:
                observation = observations[0]
                agent.initial_observation = observation
                created_at = (
                    agent.created_at
                    if isinstance(agent.created_at, (int, float))
                    else observation.observed_at
                )
                payload = {
                    "observation": model_to_dict(observation),
                    "hypothesis": build_observation_hypothesis(observation),
                    "question": "Existem observações locais disponíveis para corroborar este sinal?",
                }
                event_id = None
                incident_id = f"incident-{observation.event_id}"
                source_id = observation.source_id
            else:
                # Backwards-compatible Etapa 3 demonstration path. The Etapa 4
                # demonstration always supplies a real ObservationFeed.
                created_at = 0.0
                payload = {
                    "event_type": "suspected_activity",
                    "position": {"x": 6, "y": 9},
                    "question": "Existe evidência independente deste evento?",
                }
                event_id = "event-example-001"
                incident_id = "incident-example-001"
                source_id = "sensor-example"

            request = Message(
                message_id=f"request-{uuid.uuid4().hex}",
                message_type=MessageType.VERIFY_REQUEST,
                created_at=created_at,
                payload=payload,
                event_id=event_id,
                incident_id=incident_id,
                source_id=source_id,
                conversation_id=conversation_id,
            )
            outgoing = build_spade_message(
                agent.informant_jid,
                request,
                performative=PERFORMATIVE_REQUEST,
                conversation_id=conversation_id,
                reply_with=request.message_id,
            )
            await self.send(outgoing)
            logger.info("VERIFY_REQUEST enviada para %s", agent.informant_jid)

            response_deadline = monotonic() + RESPONSE_TIMEOUT_SECONDS
            rejected_responses: list[dict[str, object]] = []
            while True:
                remaining = response_deadline - monotonic()
                if remaining <= 0:
                    break
                incoming = await self.receive(timeout=remaining)
                if incoming is None or monotonic() >= response_deadline:
                    break
                try:
                    response = parse_spade_message(incoming)
                except (TypeError, ValueError) as error:
                    logger.warning("Resposta rejeitada: %s", error)
                    rejected_responses.append({
                        "reason": _rejected_response_reason(incoming, request),
                        "message_id": None,
                    })
                    continue
                if not response_matches_request(
                    incoming, response, request, agent.informant_jid
                ):
                    logger.warning("VERIFY_RESPONSE rejeitada: correlação ou remetente inválido")
                    rejected_responses.append({
                        "reason": "invalid_correlation",
                        "message_id": response.message_id,
                    })
                    continue
                if observations:
                    try:
                        aggregate = aggregate_verification_responses(
                            observation,
                            [response],
                            request.conversation_id,
                            request.message_id,
                            agent.max_distance,
                            agent.max_time_difference,
                            incompatibility_rules=agent.incompatibility_rules,
                            compatibility_rules=agent.compatibility_rules,
                            expected_incident_id=request.incident_id,
                        )
                        evaluation = evaluate_preliminary_corroboration(
                            aggregate, agent.eligible_source_ids
                        )
                        decision = decide_preliminary_verification(
                            evaluation, agent.minimum_compatible_sources
                        )
                    except (TypeError, ValueError) as error:
                        logger.warning("Corroboração não avaliada: %s", error)
                        rejected_responses.append({
                            "reason": "invalid_response",
                            "message_id": response.message_id,
                        })
                        continue
                    agent.aggregate_summary = aggregate
                    agent.evaluation_summary = evaluation
                    agent.decision = decision
                    _record_verification_history(
                        agent, request, observation, aggregate, evaluation, decision
                    )
                    _log_corroboration_result(observation, aggregate, evaluation, decision)
                else:
                    _record_safe_observe(agent, None, "no_initial_observation", request)
                agent.response = response
                logger.info("VERIFY_RESPONSE recebida de %s", incoming.sender)
                _record_response_wait_diagnostics(
                    agent, request, rejected_responses, timed_out=False
                )
                return

            logger.warning("Timeout à espera de VERIFY_RESPONSE")
            # Preserve the previous diagnostic reason when no valid reply follows
            # a rejection, while recording that the global wait did expire.
            reason = rejected_responses[-1]["reason"] if rejected_responses else "timeout"
            _record_safe_observe(
                agent, observation if observations else None, reason, request
            )
            _record_response_wait_diagnostics(
                agent, request, rejected_responses, timed_out=True
            )

    async def setup(self):
        template = Template(
            metadata={
                "performative": PERFORMATIVE_INFORM,
                "ontology": ONTOLOGY,
                "protocol": VERIFICATION_PROTOCOL,
            }
        )
        self.behaviour = self.VerificationBehaviour()
        self.add_behaviour(self.behaviour, template)


def _recent_observations(observation_feed) -> tuple:
    """Read a local feed without accepting arbitrary agent state."""
    recent = getattr(observation_feed, "recent", None)
    if not callable(recent):
        return ()
    try:
        return tuple(recent())
    except TypeError:
        return ()


def _rejected_response_reason(incoming: Any, request: Message) -> str:
    """Distinguish a malformed body from a valid body in another conversation."""
    try:
        candidate = Message.from_json(incoming.body)
    except (AttributeError, TypeError, ValueError):
        return "invalid_response"

    transport_conversation_id = incoming.get_metadata("conversation-id")
    if (
        candidate.conversation_id != request.conversation_id
        or transport_conversation_id != request.conversation_id
    ):
        return "invalid_correlation"
    return "invalid_response"


def _record_response_wait_diagnostics(
    agent,
    request: Message,
    rejected_responses: list[dict[str, object]],
    *,
    timed_out: bool,
) -> None:
    record = agent.verification_history[request.conversation_id][request.message_id]
    record["rejected_responses"] = tuple(rejected_responses)
    record["response_wait_timed_out"] = timed_out


def _record_safe_observe(agent, observation, reason: str, request: Message) -> None:
    """Record a conservative local result for missing or invalid responses."""
    eligible = getattr(agent, "eligible_source_ids", ())
    if not isinstance(eligible, (tuple, list, set)):
        eligible = ()
    try:
        evaluation = evaluate_preliminary_corroboration(
            {
                "classification": "no_data",
                "compatible_observation_ids": (),
                "compatible_source_ids": (),
                "source_ids": (),
            },
            eligible,
        )
        minimum = getattr(agent, "minimum_compatible_sources", None)
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum <= 0:
            minimum = 1
        decision = decide_preliminary_verification(evaluation, minimum)
        decision["decision"] = "observe"
        decision["reason"] = reason
        agent.aggregate_summary = None
        agent.evaluation_summary = evaluation
        agent.decision = decision
        _record_verification_history(
            agent,
            request,
            observation,
            {},
            evaluation,
            decision,
            classification=reason,
        )
        _log_corroboration_result(observation, {}, evaluation, decision)
    except (TypeError, ValueError):
        agent.decision = {
            "decision": "observe",
            "reason": reason,
            "compatible_observation_ids": (),
            "compatible_source_ids": (),
            "preliminary_score": None,
            "information_coverage": None,
        }
        _record_verification_history(
            agent,
            request,
            observation,
            {},
            {},
            agent.decision,
            classification=reason,
        )


def _record_verification_history(
    agent,
    request: Message,
    observation,
    aggregate,
    evaluation,
    decision,
    *,
    classification: str | None = None,
) -> None:
    """Store the minimal explainability record for one completed request."""
    history = getattr(agent, "verification_history", None)
    if not isinstance(history, dict):
        history = {}
        agent.verification_history = history

    conversation_history = history.setdefault(request.conversation_id, {})
    if request.message_id in conversation_history:
        return

    initial_observation = None
    if isinstance(observation, Observation):
        initial_observation = model_to_dict(observation)

    conversation_history[request.message_id] = {
        "conversation_id": request.conversation_id,
        "request_message_id": request.message_id,
        "initial_observation": initial_observation,
        "evidence_observation_ids": tuple(
            aggregate.get("compatible_observation_ids", ())
        ),
        "source_ids": tuple(evaluation.get("observed_source_ids", ())),
        "compatible_source_ids": tuple(
            decision.get("compatible_source_ids", ())
        ),
        "classification": classification or evaluation.get("classification"),
        "preliminary_score": decision.get("preliminary_score"),
        "information_coverage": decision.get("information_coverage"),
        "decision": decision.get("decision", "observe"),
        "reason": decision.get("reason"),
    }


def _log_corroboration_result(observation, aggregate, evaluation, decision) -> None:
    logger.info(
        "Corroboração | observação inicial=%s | observações compatíveis=%s | "
        "fontes distintas=%s | pontuação preliminar=%s | cobertura=%s | "
        "decisão=%s | razão=%s",
        getattr(observation, "event_id", None),
        aggregate.get(
            "compatible_observation_ids",
            decision.get("compatible_observation_ids", ()),
        ),
        evaluation.get("observed_source_ids", ()),
        decision.get("preliminary_score"),
        decision.get("information_coverage"),
        decision.get("decision"),
        decision.get("reason"),
    )

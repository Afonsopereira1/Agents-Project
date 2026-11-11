"""Agente informador que responde a pedidos de verificação."""

from __future__ import annotations

import logging
from math import hypot, isfinite

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.template import Template

from isia.communication.messages import Message, MessageType, model_from_dict, model_to_dict
from isia.communication.transport import (
    ONTOLOGY,
    PERFORMATIVE_INFORM,
    PERFORMATIVE_REQUEST,
    VERIFICATION_PROTOCOL,
    build_spade_message,
    parse_spade_message,
)
from isia.domain.models import Position

logger = logging.getLogger(__name__)


class InformantAgent(Agent):
    """Agente que responde apenas com evidência do seu feed local."""

    def __init__(self, jid: str, password: str):
        super().__init__(jid, password)
        self.observation_feed = None
        self.source_id: str | None = None
        self.created_at: float | None = None
        self.coverage_position = None
        self.coverage_radius = None
        self.coverage_capability = None
        self.coverage_observed_from = None
        self.coverage_observed_until = None
        self.coverage_opportunity_confirmed = False

    def set_local_observation_feed(
        self,
        observation_feed,
        source_id: str,
        created_at: float,
        *,
        coverage_position=None,
        coverage_radius=None,
        coverage_capability=None,
        coverage_observed_from=None,
        coverage_observed_until=None,
        coverage_opportunity_confirmed=False,
    ) -> None:
        """Give the agent only its local feed and local message metadata."""
        self.observation_feed = observation_feed
        self.source_id = source_id
        self.created_at = created_at
        self.coverage_position = coverage_position
        self.coverage_radius = coverage_radius
        self.coverage_capability = coverage_capability
        self.coverage_observed_from = coverage_observed_from
        self.coverage_observed_until = coverage_observed_until
        self.coverage_opportunity_confirmed = coverage_opportunity_confirmed

    class VerificationBehaviour(CyclicBehaviour):
        async def run(self):
            incoming = await self.receive(timeout=10)
            if incoming is None:
                return
            try:
                request = parse_spade_message(incoming)
            except (TypeError, ValueError) as error:
                logger.warning("Pedido rejeitado: %s", error)
                return
            if request.message_type is not MessageType.VERIFY_REQUEST:
                return

            observations = _recent_observations(self.agent.observation_feed)
            source_id = self.agent.source_id
            if not isinstance(source_id, str) or not source_id.strip():
                source_id = "informant-example"
            created_at = self.agent.created_at
            if not isinstance(created_at, (int, float)):
                created_at = request.created_at

            status = "observations_available" if observations else "no_data"
            payload = {
                "request_message_id": request.message_id,
                "observations": [model_to_dict(observation) for observation in observations],
                "status": status,
            }
            if isinstance(request.payload.get("hypothesis"), dict):
                payload["hypothesis"] = request.payload["hypothesis"]
            absence = _informative_absence_payload(self, request)
            if not observations and absence is not None:
                payload["status"] = "informative_absence"
                payload["absence"] = absence

            response = Message(
                message_id=f"response-{request.message_id}",
                message_type=MessageType.VERIFY_RESPONSE,
                created_at=created_at,
                payload=payload,
                event_id=request.event_id,
                incident_id=request.incident_id,
                source_id=source_id,
                conversation_id=request.conversation_id,
            )
            reply = build_spade_message(
                str(incoming.sender),
                response,
                performative=PERFORMATIVE_INFORM,
                conversation_id=request.conversation_id,
                in_reply_to=request.message_id,
            )
            await self.send(reply)
            logger.info("VERIFY_RESPONSE enviada para %s", incoming.sender)

    async def setup(self):
        template = Template(
            metadata={
                "performative": PERFORMATIVE_REQUEST,
                "ontology": ONTOLOGY,
                "protocol": VERIFICATION_PROTOCOL,
            }
        )
        self.add_behaviour(self.VerificationBehaviour(), template)


def _recent_observations(observation_feed) -> tuple:
    """Read only the observations exposed by the local feed."""
    recent = getattr(observation_feed, "recent", None)
    if not callable(recent):
        return ()
    try:
        return tuple(recent())
    except TypeError:
        return ()


def _informative_absence_payload(agent, request: Message) -> dict[str, object] | None:
    """Return a non-detection claim only when local coverage is configured."""
    hypothesis = request.payload.get("hypothesis")
    if not isinstance(hypothesis, dict):
        return None
    coverage_position = getattr(agent, "coverage_position", None)
    coverage_radius = getattr(agent, "coverage_radius", None)
    coverage_capability = getattr(agent, "coverage_capability", None)
    observed_from = getattr(agent, "coverage_observed_from", None)
    observed_until = getattr(agent, "coverage_observed_until", None)
    opportunity_confirmed = getattr(agent, "coverage_opportunity_confirmed", False)
    if (
        not isinstance(coverage_position, Position)
        or type(coverage_radius) not in (int, float)
        or not isinstance(coverage_capability, str)
        or not coverage_capability.strip()
        or type(observed_from) not in (int, float)
        or type(observed_until) not in (int, float)
    ):
        return None
    if opportunity_confirmed is not True:
        return None
    try:
        hypothesis_position = model_from_dict(hypothesis["position"], Position)
        hypothesis_from = hypothesis["valid_from"]
        hypothesis_until = hypothesis["valid_until"]
    except (KeyError, TypeError, ValueError):
        return None
    if (
        type(coverage_radius) not in (int, float)
        or not isfinite(coverage_radius)
        or coverage_radius < 0
        or type(observed_from) not in (int, float)
        or type(observed_until) not in (int, float)
        or not isfinite(observed_from)
        or not isfinite(observed_until)
        or observed_from > observed_until
        or type(hypothesis_from) not in (int, float)
        or type(hypothesis_until) not in (int, float)
        or not isfinite(hypothesis_from)
        or not isfinite(hypothesis_until)
        or hypothesis_from > hypothesis_until
        or observed_from > hypothesis_from
        or observed_until < hypothesis_until
        or hypot(
            coverage_position.x - hypothesis_position.x,
            coverage_position.y - hypothesis_position.y,
        ) > coverage_radius
    ):
        return None
    return {
        "hypothesis_id": hypothesis.get("hypothesis_id"),
        "declared_non_detection": True,
        "observed_from": observed_from,
        "observed_until": observed_until,
        "coverage": {
            "position": {
                "x": coverage_position.x,
                "y": coverage_position.y,
            },
            "radius": coverage_radius,
            "capability": coverage_capability,
            "capability_validated": True,
            "opportunity_confirmed": True,
        },
    }

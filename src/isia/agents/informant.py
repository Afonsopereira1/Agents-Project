"""Agente informador que responde a pedidos de verificação."""

from __future__ import annotations

import logging

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
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

logger = logging.getLogger(__name__)


class InformantAgent(Agent):
    """Agente que responde apenas com evidência do seu feed local."""

    def __init__(self, jid: str, password: str):
        super().__init__(jid, password)
        self.observation_feed = None
        self.source_id: str | None = None
        self.created_at: float | None = None

    def set_local_observation_feed(
        self, observation_feed, source_id: str, created_at: float
    ) -> None:
        """Give the agent only its local feed and local message metadata."""
        self.observation_feed = observation_feed
        self.source_id = source_id
        self.created_at = created_at

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

            response = Message(
                message_id=f"response-{request.message_id}",
                message_type=MessageType.VERIFY_RESPONSE,
                created_at=created_at,
                payload={
                    "request_message_id": request.message_id,
                    "observations": [model_to_dict(observation) for observation in observations],
                    "status": "observations_available" if observations else "no_data",
                },
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

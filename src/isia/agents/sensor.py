"""Agente sensor que inicia uma verificação e aguarda a resposta."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from spade.agent import Agent
from spade.behaviour import OneShotBehaviour
from spade.template import Template

from isia.communication.messages import Message, MessageType
from isia.communication.transport import (
    ONTOLOGY,
    PERFORMATIVE_INFORM,
    PERFORMATIVE_REQUEST,
    VERIFICATION_PROTOCOL,
    build_spade_message,
    parse_spade_message,
)

logger = logging.getLogger(__name__)


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
        self.response: Message | None = None
        self.conversation_id: str | None = None

    class VerificationBehaviour(OneShotBehaviour):
        async def run(self):
            agent: SensorAgent = self.agent  # type: ignore[assignment]
            conversation_id = f"conversation-{uuid.uuid4().hex}"
            agent.conversation_id = conversation_id
            request = Message(
                message_id=f"request-{uuid.uuid4().hex}",
                message_type=MessageType.VERIFY_REQUEST,
                created_at=0.0,
                payload={
                    "event_type": "suspected_activity",
                    "position": {"x": 6, "y": 9},
                    "question": "Existe evidência independente deste evento?",
                },
                event_id="event-example-001",
                incident_id="incident-example-001",
                source_id="sensor-example",
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

            incoming = await self.receive(timeout=10)
            if incoming is None:
                logger.warning("Timeout à espera de VERIFY_RESPONSE")
                return
            try:
                response = parse_spade_message(incoming)
            except (TypeError, ValueError) as error:
                logger.warning("Resposta rejeitada: %s", error)
                return
            if response_matches_request(
                incoming, response, request, agent.informant_jid
            ):
                agent.response = response
                logger.info("VERIFY_RESPONSE recebida de %s", incoming.sender)
            else:
                logger.warning("VERIFY_RESPONSE rejeitada: correlação ou remetente inválido")

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

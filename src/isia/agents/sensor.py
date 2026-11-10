"""Agente sensor que inicia uma verificação e aguarda a resposta."""

from __future__ import annotations

import logging
import uuid

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
            if response.message_type is MessageType.VERIFY_RESPONSE:
                agent.response = response
                logger.info("VERIFY_RESPONSE recebida de %s", incoming.sender)

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

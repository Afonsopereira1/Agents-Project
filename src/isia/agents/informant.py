"""Agente informador que responde a pedidos de verificação."""

from __future__ import annotations

import logging

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
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


class InformantAgent(Agent):
    """Agente independente com uma resposta de exemplo determinística."""

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

            response = Message(
                message_id=f"response-{request.message_id}",
                message_type=MessageType.VERIFY_RESPONSE,
                created_at=request.created_at,
                payload={
                    "request_message_id": request.message_id,
                    "verification": "example_observation_available",
                    "supports_event": True,
                },
                event_id=request.event_id,
                incident_id=request.incident_id,
                source_id="informant-example",
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

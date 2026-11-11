"""Adaptador mínimo entre o contrato JSON do projeto e o transporte SPADE."""

from __future__ import annotations

from typing import Any

from isia.communication.messages import Message

try:
    from spade.message import Message as SpadeMessage
except ImportError:  # pragma: no cover - permite importar o pacote sem SPADE instalado
    SpadeMessage = None  # type: ignore[assignment,misc]


ONTOLOGY = "isia"
VERIFICATION_PROTOCOL = "verification"
PERFORMATIVE_REQUEST = "request"
PERFORMATIVE_INFORM = "inform"
PERFORMATIVE_CFP = "cfp"
PERFORMATIVE_PROPOSE = "propose"
PERFORMATIVE_REJECT_PROPOSAL = "reject-proposal"
PERFORMATIVE_ACCEPT_PROPOSAL = "accept-proposal"
CONTRACT_NET_PROTOCOL = "contract-net"


def build_spade_message(
    recipient: str,
    body: Message,
    *,
    performative: str,
    conversation_id: str,
    reply_with: str | None = None,
    in_reply_to: str | None = None,
    protocol: str = VERIFICATION_PROTOCOL,
) -> Any:
    """Cria uma mensagem SPADE com corpo e metadados do contrato ISIA."""
    if SpadeMessage is None:
        raise RuntimeError("SPADE não está instalado. Instale requirements.txt primeiro.")
    if not isinstance(body, Message):
        raise TypeError("body deve ser isia.communication.messages.Message.")
    if body.conversation_id != conversation_id:
        raise ValueError("conversation_id do transporte e do corpo devem coincidir.")

    message = SpadeMessage(to=recipient, body=body.to_json())
    metadata = {
        "performative": performative,
        "ontology": ONTOLOGY,
        "protocol": protocol,
        "conversation-id": conversation_id,
    }
    if reply_with is not None:
        metadata["reply-with"] = reply_with
    if in_reply_to is not None:
        metadata["in-reply-to"] = in_reply_to
    for key, value in metadata.items():
        message.set_metadata(key, value)
    return message


def parse_spade_message(
    message: Any,
    *,
    expected_protocol: str = VERIFICATION_PROTOCOL,
) -> Message:
    """Valida metadados essenciais e descodifica o corpo JSON ISIA."""
    if message is None:
        raise ValueError("Mensagem SPADE ausente.")
    if message.get_metadata("ontology") != ONTOLOGY:
        raise ValueError("Ontology SPADE inesperada.")
    if message.get_metadata("protocol") != expected_protocol:
        raise ValueError("Protocol SPADE inesperado.")
    conversation_id = message.get_metadata("conversation-id")
    if not conversation_id:
        raise ValueError("conversation-id SPADE ausente.")

    body = Message.from_json(message.body)
    if body.conversation_id != conversation_id:
        raise ValueError("conversation-id SPADE e do corpo não coincidem.")
    return body

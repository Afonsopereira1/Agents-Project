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
PERFORMATIVE_REJECT_PROPOSAL = "reject-proposal"  # iniciador → propostas não escolhidas
PERFORMATIVE_REFUSE = "refuse"  # recurso → iniciador: recusa do CFP (FIPA Contract Net)
PERFORMATIVE_ACCEPT_PROPOSAL = "accept-proposal"
CONTRACT_NET_PROTOCOL = "contract-net"


def bare_jid(value: object) -> str:
    """Devolver o JID sem recurso e em minúsculas, para comparar remetentes.

    Args:
        value (object): JID, em texto ou objeto JID do SPADE (ex.: ``msg.sender``).

    Returns:
        str: Parte ``utilizador@domínio`` do JID, em minúsculas.
    """
    return str(value).split("/", 1)[0].lower()


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
    """Criar uma mensagem SPADE com o corpo e os metadados do contrato ISIA.

    Args:
        recipient (str): JID do destinatário.
        body (Message): Mensagem ISIA, enviada como JSON no corpo.
        performative (str): Performativa FIPA (uma das constantes ``PERFORMATIVE_*``).
        conversation_id (str): Conversa; tem de coincidir com a do ``body``.
        reply_with (str | None): Valor de ``reply-with``; omitido se ``None``.
        in_reply_to (str | None): Valor de ``in-reply-to``; omitido se ``None``.
        protocol (str): Protocolo FIPA, por omissão o de verificação.

    Returns:
        Any: ``spade.message.Message`` com corpo e metadados preenchidos.

    Raises:
        RuntimeError: Se o SPADE não estiver instalado.
        TypeError: Se ``body`` não for uma ``Message``.
        ValueError: Se ``conversation_id`` não coincidir com o do ``body``.
    """
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
    """Validar os metadados essenciais e descodificar o corpo JSON ISIA.

    Args:
        message (Any): Mensagem SPADE recebida, ou ``None`` se o ``receive`` expirou.
        expected_protocol (str): Protocolo FIPA que a mensagem tem de declarar.

    Returns:
        Message: Corpo descodificado e validado.

    Raises:
        ValueError: Se a mensagem faltar, a ontologia, o protocolo ou o ``conversation-id``
            forem inesperados, ou este não coincidir com o do corpo.
        TypeError: Se o corpo JSON não for um objeto ou o payload não for um dicionário.
    """
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

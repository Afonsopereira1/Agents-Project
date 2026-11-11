import unittest

from isia.communication.messages import Message, MessageType


try:
    from spade.message import Message as SpadeMessage
    from isia.communication.transport import build_spade_message, parse_spade_message
except ImportError:  # SPADE é uma dependência opcional para os testes locais do contrato.
    SpadeMessage = None


@unittest.skipUnless(SpadeMessage is not None, "SPADE 4.1.4 não está instalado")
class TestMessagingContract(unittest.TestCase):
    def make_body(self):
        return Message(
            "request-001", MessageType.VERIFY_REQUEST, 0.0,
            {"question": "há evidência?"}, event_id="event-001",
            incident_id="incident-001", source_id="sensor-example",
            conversation_id="conversation-001",
        )

    def test_transporte_preserva_corpo_e_conversa(self):
        body = self.make_body()
        outgoing = build_spade_message(
            "informant@localhost", body, performative="request",
            conversation_id="conversation-001", reply_with=body.message_id,
        )
        self.assertEqual(outgoing.to, "informant@localhost")
        self.assertEqual(outgoing.get_metadata("ontology"), "isia")
        self.assertEqual(outgoing.get_metadata("protocol"), "verification")
        self.assertEqual(outgoing.get_metadata("conversation-id"), "conversation-001")
        self.assertEqual(parse_spade_message(outgoing).to_dict(), body.to_dict())

    def test_transporte_rejeita_conversa_inconsistente(self):
        body = self.make_body()
        outgoing = build_spade_message(
            "informant@localhost", body, performative="request",
            conversation_id="conversation-001",
        )
        outgoing.set_metadata("conversation-id", "other-conversation")
        with self.assertRaises(ValueError):
            parse_spade_message(outgoing)

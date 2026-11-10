import unittest

from isia.communication.messages import Message, MessageType


try:
    from isia.agents.sensor import response_matches_request
except ImportError:
    response_matches_request = None


class IncomingMessage:
    def __init__(self, sender, conversation_id, in_reply_to):
        self.sender = sender
        self.metadata = {
            "conversation-id": conversation_id,
            "in-reply-to": in_reply_to,
        }

    def get_metadata(self, name):
        return self.metadata.get(name)


@unittest.skipUnless(response_matches_request is not None, "SPADE não está instalado")
class TestSensorResponseValidation(unittest.TestCase):
    def setUp(self):
        self.request = Message(
            "request-001", MessageType.VERIFY_REQUEST, 0.0,
            {"question": "há evidência?"}, conversation_id="conversation-001",
        )

    def make_response(self, **changes):
        values = {
            "conversation_id": self.request.conversation_id,
            "request_message_id": self.request.message_id,
            "sender": "informant@localhost",
            "in_reply_to": self.request.message_id,
        }
        values.update(changes)
        response = Message(
            "response-001", MessageType.VERIFY_RESPONSE, 0.0,
            {"request_message_id": values["request_message_id"]},
            conversation_id=values["conversation_id"],
        )
        incoming = IncomingMessage(
            values["sender"], values["conversation_id"], values["in_reply_to"]
        )
        return incoming, response

    def test_resposta_valida(self):
        incoming, response = self.make_response()
        self.assertTrue(
            response_matches_request(
                incoming, response, self.request, "informant@localhost"
            )
        )

    def test_rejeita_conversation_id_incorreto(self):
        incoming, response = self.make_response(conversation_id="other-conversation")
        self.assertFalse(
            response_matches_request(
                incoming, response, self.request, "informant@localhost"
            )
        )

    def test_rejeita_in_reply_to_incorreto(self):
        incoming, response = self.make_response(in_reply_to="other-request")
        self.assertFalse(
            response_matches_request(
                incoming, response, self.request, "informant@localhost"
            )
        )

    def test_rejeita_request_message_id_incorreto(self):
        incoming, response = self.make_response(request_message_id="other-request")
        self.assertFalse(
            response_matches_request(
                incoming, response, self.request, "informant@localhost"
            )
        )

    def test_rejeita_remetente_incorreto(self):
        incoming, response = self.make_response(sender="other@localhost")
        self.assertFalse(
            response_matches_request(
                incoming, response, self.request, "informant@localhost"
            )
        )

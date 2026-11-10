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
class TestIndependentVerificationConversations(unittest.TestCase):
    def make_exchange(self, suffix):
        request = Message(
            f"request-{suffix}",
            MessageType.VERIFY_REQUEST,
            0.0,
            {"question": f"há evidência em {suffix}?"},
            conversation_id=f"conversation-{suffix}",
        )
        response = Message(
            f"response-{suffix}",
            MessageType.VERIFY_RESPONSE,
            0.0,
            {"request_message_id": request.message_id},
            conversation_id=request.conversation_id,
        )
        incoming = IncomingMessage(
            "informant@localhost",
            request.conversation_id,
            request.message_id,
        )
        return request, response, incoming

    def test_respostas_fora_de_ordem_sao_aceites_na_conversa_certa(self):
        request_a, response_a, incoming_a = self.make_exchange("a")
        request_b, response_b, incoming_b = self.make_exchange("b")

        received_out_of_order = [
            (incoming_b, response_b, request_b),
            (incoming_a, response_a, request_a),
        ]

        accepted = [
            response_matches_request(
                incoming,
                response,
                request,
                "informant@localhost",
            )
            for incoming, response, request in received_out_of_order
        ]

        self.assertEqual(accepted, [True, True])

    def test_resposta_de_a_nao_e_aceite_para_b_e_vice_versa(self):
        request_a, response_a, incoming_a = self.make_exchange("a")
        request_b, response_b, incoming_b = self.make_exchange("b")

        self.assertFalse(
            response_matches_request(
                incoming_a, response_a, request_b, "informant@localhost"
            )
        )
        self.assertFalse(
            response_matches_request(
                incoming_b, response_b, request_a, "informant@localhost"
            )
        )

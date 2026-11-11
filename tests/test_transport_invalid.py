import unittest

from isia.communication.messages import Message, MessageType
from isia.communication.transport import parse_spade_message


class FakeSpadeMessage:
    def __init__(self, body, **metadata):
        self.body = body
        self.metadata = metadata

    def get_metadata(self, name):
        return self.metadata.get(name)


class TestInvalidTransportMessages(unittest.TestCase):
    def make_message(self, body, conversation_id="conversation-001"):
        return FakeSpadeMessage(
            body,
            ontology="isia",
            protocol="verification",
            **{"conversation-id": conversation_id},
        )

    def make_valid_body(self, conversation_id="conversation-001"):
        return Message(
            "request-001",
            MessageType.VERIFY_REQUEST,
            0.0,
            {"question": "há evidência?"},
            conversation_id=conversation_id,
        ).to_json()

    def test_rejeita_json_malformado(self):
        with self.assertRaises(ValueError):
            parse_spade_message(self.make_message("not-json"))

    def test_rejeita_campos_obrigatorios_em_falta(self):
        with self.assertRaises(ValueError):
            parse_spade_message(self.make_message('{"schema_version": 1}'))

    def test_rejeita_conversation_id_incompativel(self):
        with self.assertRaises(ValueError):
            parse_spade_message(
                self.make_message(self.make_valid_body("body-conversation"))
            )


if __name__ == "__main__":
    unittest.main()

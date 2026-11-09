import unittest

from isia.communication.messages import (
    Message,
    MessageDeduplicator,
    MessageType,
    deserialize_model,
    model_from_dict,
    model_to_dict,
    serialize_model,
)
from isia.domain.models import (
    Bid,
    Incident,
    Mission,
    MissionStatus,
    Observation,
    Position,
    ResourceState,
    ResourceStatus,
)


class TestMessages(unittest.TestCase):
    def make_message(self):
        return Message(
            "msg-001",
            MessageType.ALERT,
            120.0,
            {"confidence_score": 0.8},
            event_id="obs-001",
            incident_id="incident-001",
            source_id="sensor-001",
            conversation_id="conversation-001",
        )

    def test_mensagem_round_trip_json(self):
        message = self.make_message()
        result = Message.from_json(message.to_json())

        self.assertEqual(result.to_dict(), message.to_dict())
        self.assertIs(result.message_type, MessageType.ALERT)

    def test_campos_obrigatorios(self):
        with self.assertRaises(ValueError):
            Message.from_dict({"message_id": "msg-001"})

    def test_validacao_da_mensagem(self):
        with self.assertRaises(ValueError):
            Message("", MessageType.ALERT, 1.0, {})
        with self.assertRaises(TypeError):
            Message("msg-001", "ALERT", 1.0, {})
        with self.assertRaises(ValueError):
            Message("msg-001", MessageType.ALERT, float("nan"), {})
        with self.assertRaises(TypeError):
            Message("msg-001", MessageType.ALERT, 1.0, [])
        with self.assertRaises(ValueError):
            Message("msg-001", MessageType.ALERT, 1.0, {}, schema_version=2)

    def test_tipo_de_mensagem_invalido(self):
        with self.assertRaises(ValueError):
            Message.from_dict(
                {
                    "schema_version": 1,
                    "message_id": "msg-001",
                    "message_type": "UNKNOWN",
                    "created_at": 1.0,
                    "payload": {},
                }
            )

    def test_deduplicacao_por_message_id(self):
        message = self.make_message()
        duplicate = Message.from_dict(message.to_dict())
        registry = MessageDeduplicator()

        self.assertTrue(registry.accept(message))
        self.assertFalse(registry.accept(duplicate))
        self.assertTrue(registry.is_duplicate("msg-001"))
        self.assertEqual(len(registry), 1)

    def test_deduplicador_rejeita_tipo_invalido(self):
        with self.assertRaises(TypeError):
            MessageDeduplicator().accept("not-a-message")

    def test_modelos_de_dominio_round_trip(self):
        observation = Observation("obs-001", "sensor-001", "sound", Position(2, 3), 15.0, 0.8)
        models = (
            Position(2, 3),
            observation,
            Incident("incident-001", (observation,)),
            ResourceState("drone-001", "drone", Position(2, 3), False, 80.0, ResourceStatus.RESERVED),
            Mission("mission-001", "incident-001", "verify", Position(2, 3), "mobile", 1, MissionStatus.RESERVED),
            Bid("mission-001", "drone-001", 5.0, 20.0, 0.2),
        )
        model_types = (Position, Observation, Incident, ResourceState, Mission, Bid)

        for model, model_type in zip(models, model_types):
            with self.subTest(model_type=model_type):
                restored = deserialize_model(serialize_model(model), model_type)
                self.assertEqual(restored, model)

    def test_modelo_desconhecido_e_dados_invalidos(self):
        with self.assertRaises(TypeError):
            model_to_dict("not-a-model")
        with self.assertRaises(ValueError):
            model_from_dict({"x": 1}, Position)
        with self.assertRaises(ValueError):
            deserialize_model("not-json", Position)


if __name__ == "__main__":
    unittest.main()

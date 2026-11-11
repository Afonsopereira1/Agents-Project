"""Regressões: ausência informativa, conflito misto e separação de incidentes."""
import unittest

from isia.communication.messages import Message, MessageType, model_to_dict
from isia.domain.models import Observation, Position
from isia.reasoning.corroboration import (
    aggregate_verification_responses,
    capability_supports_signal,
    classify_verification_response,
    decide_preliminary_verification,
    evaluate_preliminary_corroboration,
)


def observation(observation_id, kind, source="sensor-02", at=10.0):
    return Observation(observation_id, source, kind, Position(5, 5), at, 0.8)


def response(observations, *, message_id="response-1", relation=None,
             incident_id="incident-1", conversation_id="conv-1", request_id="req-1"):
    hypothesis = {
        "hypothesis_id": "hypothesis-obs-0",
        "event_type": "gunshot_like_sound",
        "position": {"x": 5, "y": 5},
        "valid_from": 10.0, "valid_until": 10.0,
    }
    payload = {
        "request_message_id": request_id,
        "status": "observations_available" if observations else "no_data",
        "observations": [model_to_dict(item) for item in observations],
        "hypothesis": hypothesis,
    }
    if relation is not None:
        payload["evidence_relation"] = relation
    return Message(message_id, MessageType.VERIFY_RESPONSE, 10.0, payload,
                   incident_id=incident_id, source_id="sensor-02",
                   conversation_id=conversation_id)


class TestCorroborationSemanticRegressions(unittest.TestCase):
    def setUp(self):
        self.initial = observation("obs-0", "gunshot_like_sound", "sensor-01")
        self.incompatible = {"gunshot_like_sound": {"suspicious_movement"}}

    def classify(self, item):
        return classify_verification_response(
            self.initial, item, 2.0, 2.0, incompatibility_rules=self.incompatible
        )

    def aggregate(self, items, **extra):
        return aggregate_verification_responses(
            self.initial, items, "conv-1", "req-1", 2.0, 2.0,
            incompatibility_rules=self.incompatible,
            expected_incident_id="incident-1", **extra
        )

    def test_capacidades_do_simulador_sao_exatas(self):
        self.assertTrue(capability_supports_signal("acoustic", "gunshot_like_sound"))
        self.assertTrue(capability_supports_signal("visual", "suspicious_movement"))
        self.assertTrue(capability_supports_signal("human", "suspicious_activity_report"))
        self.assertFalse(capability_supports_signal("visual", "gunshot_like_sound"))
        self.assertFalse(capability_supports_signal("unknown", "gunshot_like_sound"))
        self.assertFalse(capability_supports_signal("acoustic", "unknown_event"))
        self.assertFalse(capability_supports_signal(None, "gunshot_like_sound"))

    def test_resposta_apenas_compativel(self):
        item = response([observation("obs-good", "gunshot_like_sound")])
        self.assertEqual(self.classify(item)["classification"], "compatible")
        self.assertEqual(self.aggregate([item])["compatible_observation_ids"], ("obs-good",))

    def test_resposta_apenas_contraditoria(self):
        item = response([observation("obs-bad", "suspicious_movement")], relation="contradictory")
        self.assertEqual(self.classify(item)["classification"], "contradictory")
        self.assertEqual(self.aggregate([item])["contradictory_observation_ids"], ("obs-bad",))

    def test_sem_regra_nao_e_contradicao(self):
        item = response([observation("obs-bad", "suspicious_movement")], relation="contradictory")
        result = classify_verification_response(self.initial, item, 2.0, 2.0)
        self.assertEqual(result["classification"], "inconclusive")

    def test_evidencia_mista_dentro_de_uma_resposta(self):
        good = observation("obs-good", "gunshot_like_sound")
        bad = observation("obs-bad", "suspicious_movement", "sensor-03")
        item = response([good, bad], relation="contradictory")
        classification = self.classify(item)
        self.assertEqual(classification["classification"], "inconclusive")
        self.assertEqual(classification["compatible_observation_ids"], ("obs-good",))
        self.assertEqual(classification["contradictory_observation_ids"], ("obs-bad",))
        aggregate = self.aggregate([item])
        self.assertEqual(aggregate["classification"], "inconclusive")
        self.assertEqual(aggregate["compatible_observation_ids"], ("obs-good",))
        self.assertEqual(aggregate["contradictory_observation_ids"], ("obs-bad",))
        self.assertEqual(aggregate["compatible_source_count"], 1)

    def test_mensagens_mistas_e_duplicados_nao_geram_contagens_extra(self):
        mixed = response([
            observation("obs-good", "gunshot_like_sound"),
            observation("obs-good", "gunshot_like_sound"),
            observation("obs-bad", "suspicious_movement", "sensor-03"),
        ], relation="contradictory")
        compatible = response([observation("obs-good", "gunshot_like_sound")],
                              message_id="response-2")
        result = self.aggregate([mixed, mixed, compatible])
        self.assertEqual(result["classification"], "inconclusive")
        self.assertEqual(result["observation_ids"], ("obs-bad", "obs-good"))
        self.assertEqual(result["compatible_observation_ids"], ("obs-good",))
        self.assertEqual(result["contradictory_observation_ids"], ("obs-bad",))
        self.assertEqual(result["compatible_source_count"], 1)

    def test_incidente_estranho_rejeitado_mesmo_na_conversa_certa(self):
        item = response([observation("obs-good", "gunshot_like_sound")],
                        incident_id="another-incident")
        with self.assertRaisesRegex(ValueError, "another incident"):
            self.aggregate([item])

    def test_conversa_e_pedido_estranhos_rejeitados(self):
        with self.assertRaises(ValueError):
            self.aggregate([response([observation("o", "gunshot_like_sound")],
                                     conversation_id="other")])
        with self.assertRaises(ValueError):
            self.aggregate([response([observation("o", "gunshot_like_sound")],
                                     request_id="other")])

    def test_conflito_pode_justificar_verificacao_movel_sem_confirmar_ameaca(self):
        item = response([
            observation("obs-good", "gunshot_like_sound"),
            observation("obs-bad", "suspicious_movement", "sensor-03"),
        ], relation="contradictory")
        aggregate = self.aggregate([item])
        evaluation = evaluate_preliminary_corroboration(aggregate, ("sensor-02", "sensor-03"))
        action = decide_preliminary_verification(evaluation, 1)
        self.assertEqual(aggregate["classification"], "inconclusive")
        self.assertEqual(action["decision"], "request_mobile_verification")


if __name__ == "__main__":
    unittest.main()

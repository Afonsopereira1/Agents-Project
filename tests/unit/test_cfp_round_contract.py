"""Contrato opcional de ordenação explícita das rondas Contract Net."""

import json
import unittest

from isia.communication.messages import Message
from isia.domain.models import Mission, Position
from isia.reasoning.allocation import build_cfp_message


class TestCfpRoundContract(unittest.TestCase):
    def setUp(self):
        self.mission = Mission(
            "mission-round", "incident-round", "verify_incident", Position(3, 4),
            "mobile_verification", 2,
        )

    def cfp(self, **kwargs):
        return build_cfp_message(
            self.mission, 20.0, 35.0,
            message_id="cfp-round", conversation_id="conversation-round", **kwargs,
        )

    def test_default_and_explicit_none_preserve_legacy_payload(self):
        expected = {
            "task": "verify_incident",
            "target": {"x": 3, "y": 4},
            "required_capability": "mobile_verification",
            "priority": 2,
            "deadline": 35.0,
        }
        self.assertEqual(self.cfp().payload, expected)
        self.assertEqual(self.cfp(round_number=None).payload, expected)

    def test_positive_integer_round_survives_json_round_trip(self):
        for round_number in (1, 2, 10):
            with self.subTest(round_number=round_number):
                cfp = self.cfp(round_number=round_number)
                self.assertEqual(cfp.payload["round_number"], round_number)
                restored = Message.from_json(cfp.to_json())
                self.assertEqual(restored.to_dict(), cfp.to_dict())
                self.assertIs(type(restored.payload["round_number"]), int)

    def test_builder_rejects_nonpositive_or_noninteger_rounds(self):
        for round_number in (0, -1, True, False, 1.0, "1", [], {}):
            with self.subTest(round_number=round_number):
                with self.assertRaisesRegex(ValueError, "round_number"):
                    self.cfp(round_number=round_number)

    def test_raw_json_rejects_invalid_rounds_including_explicit_null(self):
        for round_number in (None, 0, -1, True, False, 1.0, "1", [], {}):
            with self.subTest(round_number=round_number):
                data = self.cfp().to_dict()
                data["payload"]["round_number"] = round_number
                with self.assertRaisesRegex(ValueError, "round_number"):
                    Message.from_json(json.dumps(data))


if __name__ == "__main__":
    unittest.main()

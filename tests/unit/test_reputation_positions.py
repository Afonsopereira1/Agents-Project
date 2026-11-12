"""Uma referência espacial tem de cumprir o contrato Position para ensinar."""

import unittest

from isia.communication.messages import Message, MessageType
from isia.domain.models import Observation, Position
from isia.reasoning.reputation import ReputationBook, result_from_mission


_MISSING = object()


class TestMissionPositionCoverage(unittest.TestCase):
    def setUp(self):
        self.observation = Observation(
            "observation", "sensor", "gunshot_like_sound", Position(1, 1), 10.0, 0.8,
        )

    def message(self, position=_MISSING, *, completed_at=14.0):
        payload = {
            "outcome": "confirmed", "reason": "local_inspection", "completed_at": completed_at,
            "task": "verify_incident", "resource_id": "drone", "accept_message_id": "accept",
        }
        if position is not _MISSING:
            payload["position"] = position
        message = Message(
            "result", MessageType.MISSION_RESULT, max(15.0, completed_at), payload,
            incident_id="incident", mission_id="mission", source_id="drone",
            conversation_id="conversation",
        )
        return Message.from_json(message.to_json())

    def update(self, message, *, book=None, max_distance=1, max_delay_seconds=30):
        evaluation = result_from_mission(
            message, self.observation, "incident", max_distance=max_distance,
            max_delay_seconds=max_delay_seconds,
        )
        book = book if book is not None else ReputationBook()
        return book.update(self.observation, "incident", evaluation)

    def assert_no_learning(self, message, *, max_distance=1):
        book = ReputationBook()
        record = self.update(message, book=book, max_distance=max_distance)
        self.assertEqual((record["updated"], record["reason"]), (False, "insufficient_reference"))
        self.assertEqual(book.score("sensor"), 0.5)

    def test_boolean_coordinates_are_not_exact_spatial_coverage(self):
        for position in ({"x": True, "y": True}, {"x": 1, "y": True}, {"x": True, "y": 1}):
            with self.subTest(position=position):
                self.assert_no_learning(self.message(position), max_distance=0)

    def test_non_integer_and_negative_coordinates_do_not_teach(self):
        for position in ({"x": 1.0, "y": 1}, {"x": 1, "y": 1.0},
                         {"x": "1", "y": 1}, {"x": 1, "y": "1"},
                         {"x": -1, "y": 1}, {"x": 1, "y": -1}):
            with self.subTest(position=position):
                self.assert_no_learning(self.message(position), max_distance=10)

    def test_malformed_position_does_not_teach(self):
        for position in (None, [], [1, 1], "1,1", {"x": 1}, {"x": 1, "y": 1, "extra": 0}):
            with self.subTest(position=position):
                self.assert_no_learning(self.message(position))

    def test_legacy_result_without_position_is_still_operational_but_not_a_reference(self):
        message = self.message()
        self.assertEqual(message.payload["outcome"], "confirmed")
        self.assertNotIn("position", message.payload)
        self.assert_no_learning(message)

    def test_valid_position_with_zero_limits_can_teach(self):
        record = self.update(self.message({"x": 1, "y": 1}, completed_at=10.0),
                             max_distance=0, max_delay_seconds=0)
        self.assertEqual((record["updated"], record["after"]), (True, 0.6))

    def test_spatial_and_temporal_coverage_limits_remain_inclusive(self):
        for position, completed_at, accepted in (
            ({"x": 0, "y": 1}, 40.0, True),
            ({"x": 2, "y": 1}, 40.0, True),
            ({"x": 2, "y": 1}, 40.001, False),
            ({"x": 3, "y": 1}, 40.0, False),
            ({"x": 1, "y": 1}, 9.0, False),
        ):
            with self.subTest(position=position, completed_at=completed_at):
                record = self.update(self.message(position, completed_at=completed_at))
                self.assertEqual(record["updated"], accepted)
                self.assertEqual(record["after"], 0.6 if accepted else 0.5)

    def test_invalid_reference_does_not_block_a_later_valid_reference(self):
        book = ReputationBook()
        rejected = self.update(self.message({"x": True, "y": True}), book=book)
        self.assertFalse(rejected["updated"])
        accepted = self.update(self.message({"x": 1, "y": 1}), book=book)
        self.assertEqual((accepted["updated"], accepted["after"]), (True, 0.6))


if __name__ == "__main__":
    unittest.main()

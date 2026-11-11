import unittest

from isia.domain.models import Incident, MissionStatus, Observation, Position
from isia.reasoning.allocation import MissionRegistry


def observation(event_id="event-1", position=(4, 7)):
    return Observation(
        event_id=event_id,
        source_id="sensor-1",
        event_type="gunshot_like_sound",
        position=Position(*position),
        observed_at=10.0,
        confidence_score=0.9,
    )


class TestMissionRegistry(unittest.TestCase):
    def setUp(self):
        self.incident = Incident("incident-7", (observation(),))
        self.registry = MissionRegistry()

    def test_request_mobile_verification_creates_mission_linked_to_incident(self):
        mission = self.registry.create_from_decision(
            self.incident,
            {"decision": "request_mobile_verification"},
            priority=2,
        )

        self.assertEqual(mission.incident_id, "incident-7")
        self.assertEqual(mission.target, Position(4, 7))
        self.assertEqual(mission.task, "verify_incident")
        self.assertEqual(mission.required_capability, "mobile_verification")
        self.assertEqual(mission.priority, 2)
        self.assertEqual(mission.status, MissionStatus.PROPOSED)

    def test_repeated_decision_returns_same_mission(self):
        decision = {"decision": "request_mobile_verification"}

        first = self.registry.create_from_decision(self.incident, decision)
        second = self.registry.create_from_decision(self.incident, decision)

        self.assertIs(first, second)
        self.assertEqual(first.mission_id, "mission-incident-7-mobile-verification")

    def test_non_mobile_decision_does_not_create_mission(self):
        self.assertIsNone(
            self.registry.create_from_decision(
                self.incident,
                {"decision": "observe"},
            )
        )

    def test_explicit_target_and_mission_id_are_preserved(self):
        mission = self.registry.create_from_decision(
            self.incident,
            {"decision": "request_mobile_verification"},
            mission_id="mission-custom-1",
            target=Position(9, 3),
        )

        self.assertEqual(mission.mission_id, "mission-custom-1")
        self.assertEqual(mission.target, Position(9, 3))


if __name__ == "__main__":
    unittest.main()

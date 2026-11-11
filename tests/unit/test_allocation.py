import unittest

from isia.communication.messages import Message, MessageType, model_to_dict
from isia.domain.models import (
    Bid,
    Incident,
    MissionStatus,
    Observation,
    Position,
    ResourceState,
    ResourceStatus,
)
from isia.reasoning.allocation import (
    MissionRegistry,
    build_cfp_message,
    evaluate_cfp,
    select_best_proposal,
)


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

    def test_build_cfp_contains_mission_contract_and_correlation_ids(self):
        mission = self.registry.create_from_decision(
            self.incident,
            {"decision": "request_mobile_verification"},
            priority=2,
        )

        cfp = build_cfp_message(
            mission,
            created_at=20.0,
            deadline=35.0,
            message_id="message-cfp-1",
            conversation_id="conversation-1",
        )

        self.assertIs(cfp.message_type, MessageType.CFP)
        self.assertEqual(cfp.message_id, "message-cfp-1")
        self.assertEqual(cfp.conversation_id, "conversation-1")
        self.assertEqual(cfp.mission_id, mission.mission_id)
        self.assertEqual(cfp.incident_id, mission.incident_id)
        self.assertEqual(
            cfp.payload,
            {
                "task": mission.task,
                "target": {"x": mission.target.x, "y": mission.target.y},
                "required_capability": mission.required_capability,
                "priority": mission.priority,
                "deadline": 35.0,
            },
        )

    def test_cfp_round_trip_json_preserves_contract(self):
        mission = self.registry.create_from_decision(
            self.incident,
            {"decision": "request_mobile_verification"},
        )
        cfp = build_cfp_message(mission, 20.0, 35.0)

        restored = Message.from_json(cfp.to_json())

        self.assertEqual(restored.to_dict(), cfp.to_dict())
        self.assertEqual(restored.mission_id, mission.mission_id)
        self.assertEqual(restored.incident_id, mission.incident_id)
        self.assertEqual(restored.conversation_id, cfp.conversation_id)

    def test_cfp_gera_ids_quando_nao_sao_fornecidos(self):
        mission = self.registry.create_from_decision(
            self.incident,
            {"decision": "request_mobile_verification"},
        )

        cfp = build_cfp_message(mission, 20.0, 35.0)

        self.assertTrue(cfp.message_id.startswith("message-"))
        self.assertTrue(cfp.conversation_id.startswith("conversation-"))

    def test_cfp_rejeita_tempo_invalido(self):
        mission = self.registry.create_from_decision(
            self.incident,
            {"decision": "request_mobile_verification"},
        )

        invalid_times = (-1.0, float("nan"), float("inf"), True, "20")
        for invalid in invalid_times:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                build_cfp_message(mission, invalid, 35.0)

        with self.assertRaises(ValueError):
            build_cfp_message(mission, 20.0, 19.0)

    def test_cfp_rejeita_missao_invalida(self):
        with self.assertRaises(TypeError):
            build_cfp_message("not-a-mission", 20.0, 35.0)

    def test_cfp_rejeita_ids_fornecidos_vazios(self):
        mission = self.registry.create_from_decision(
            self.incident,
            {"decision": "request_mobile_verification"},
        )

        with self.assertRaises(ValueError):
            build_cfp_message(mission, 20.0, 35.0, message_id="")
        with self.assertRaises(ValueError):
            build_cfp_message(mission, 20.0, 35.0, conversation_id="")

    def _cfp(self, deadline=35.0):
        mission = self.registry.create_from_decision(
            self.incident,
            {"decision": "request_mobile_verification"},
        )
        return build_cfp_message(
            mission,
            created_at=20.0,
            deadline=deadline,
            message_id="cfp-1",
            conversation_id="conversation-1",
        )

    def _resource(self, *, available=True, autonomy=80.0, status=None):
        return ResourceState(
            "drone-1",
            "drone",
            Position(1, 2),
            available,
            autonomy,
            status,
        )

    def test_evaluate_cfp_builds_bid_without_reserving_resource(self):
        resource = self._resource()
        response = evaluate_cfp(
            self._cfp(),
            resource,
            ("mobile_verification",),
            current_time=21.0,
            minimum_autonomy_percent=20.0,
            eta_seconds=4.0,
            energy_cost_percent=10.0,
            load=0.25,
        )

        self.assertIs(response.message_type, MessageType.PROPOSAL)
        self.assertEqual(response.mission_id, "mission-incident-7-mobile-verification")
        self.assertEqual(response.incident_id, "incident-7")
        self.assertEqual(response.conversation_id, "conversation-1")
        self.assertEqual(response.source_id, "drone-1")
        self.assertEqual(response.payload["cfp_message_id"], "cfp-1")
        self.assertEqual(response.payload["bid"]["resource_id"], "drone-1")
        self.assertEqual(resource.status, ResourceStatus.AVAILABLE)

    def test_evaluate_cfp_rejects_ineligible_resources(self):
        cases = (
            (self._resource(available=False, status=ResourceStatus.UNAVAILABLE), ("mobile_verification",), 20.0, "resource_unavailable"),
            (self._resource(), ("thermal_scan",), 20.0, "capability_mismatch"),
            (self._resource(autonomy=25.0), ("mobile_verification",), 20.0, "autonomy_insufficient"),
        )
        for resource, capabilities, minimum, reason in cases:
            with self.subTest(reason=reason):
                response = evaluate_cfp(
                    self._cfp(),
                    resource,
                    capabilities,
                    current_time=21.0,
                    minimum_autonomy_percent=minimum,
                    eta_seconds=4.0,
                    energy_cost_percent=10.0,
                    load=0.25,
                )
                self.assertIs(response.message_type, MessageType.REJECT)
                self.assertEqual(response.payload["reason"], reason)
                self.assertEqual(response.payload["cfp_message_id"], "cfp-1")

    def test_evaluate_cfp_rejects_expired_and_invalid_messages(self):
        expired = evaluate_cfp(
            self._cfp(deadline=25.0),
            self._resource(),
            ("mobile_verification",),
            current_time=26.0,
            minimum_autonomy_percent=20.0,
            eta_seconds=4.0,
            energy_cost_percent=10.0,
            load=0.25,
        )
        self.assertIs(expired.message_type, MessageType.REJECT)
        self.assertEqual(expired.payload["reason"], "cfp_expired")

        invalid = Message(
            "alert-1",
            MessageType.ALERT,
            20.0,
            {},
            conversation_id="conversation-1",
        )
        with self.assertRaises(ValueError):
            evaluate_cfp(
                invalid,
                self._resource(),
                ("mobile_verification",),
                current_time=21.0,
                minimum_autonomy_percent=20.0,
                eta_seconds=4.0,
                energy_cost_percent=10.0,
                load=0.25,
            )

    def _proposal(
        self,
        cfp,
        resource_id,
        *,
        eta=10.0,
        energy_cost=20.0,
        load=0.2,
        message_id=None,
        created_at=21.0,
        **overrides,
    ):
        bid = Bid(cfp.mission_id, resource_id, eta, energy_cost, load)
        values = {
            "message_id": message_id or f"proposal-{resource_id}",
            "message_type": MessageType.PROPOSAL,
            "created_at": created_at,
            "payload": {
                "cfp_message_id": cfp.message_id,
                "bid": model_to_dict(bid),
            },
            "incident_id": cfp.incident_id,
            "mission_id": cfp.mission_id,
            "source_id": resource_id,
            "conversation_id": cfp.conversation_id,
        }
        values.update(overrides)
        return Message(**values)

    def test_selects_lowest_normalized_cost_not_first_response(self):
        cfp = self._cfp()
        slower = self._proposal(
            cfp, "resource-slow", eta=30.0, energy_cost=40.0, load=0.5
        )
        faster = self._proposal(
            cfp, "resource-fast", eta=10.0, energy_cost=20.0, load=0.2
        )

        selection = select_best_proposal(cfp, (slower, faster))

        self.assertEqual(selection.reason, "proposal_selected")
        self.assertEqual(selection.winner_bid.resource_id, "resource-fast")
        self.assertEqual(selection.winner.message_id, "proposal-resource-fast")
        self.assertAlmostEqual(selection.winner_cost, 17 / 30)
        self.assertEqual(len(selection.valid_proposals), 2)

    def test_equal_cost_uses_resource_id_as_tiebreaker(self):
        cfp = self._cfp()
        resource_b = self._proposal(cfp, "resource-b")
        resource_a = self._proposal(cfp, "resource-a")

        selection = select_best_proposal(cfp, (resource_b, resource_a))

        self.assertEqual(selection.winner_bid.resource_id, "resource-a")

    def test_no_valid_proposals_is_explicit(self):
        cfp = self._cfp()
        rejected = Message(
            "reject-1",
            MessageType.REJECT,
            21.0,
            {"cfp_message_id": cfp.message_id, "reason": "resource_unavailable"},
            incident_id=cfp.incident_id,
            mission_id=cfp.mission_id,
            source_id="resource-1",
            conversation_id=cfp.conversation_id,
        )

        selection = select_best_proposal(cfp, (rejected,))

        self.assertIsNone(selection.winner)
        self.assertIsNone(selection.winner_bid)
        self.assertIsNone(selection.winner_cost)
        self.assertEqual(selection.valid_proposals, ())
        self.assertEqual(selection.reason, "no_valid_proposals")

    def test_ignores_invalid_duplicate_and_late_proposals(self):
        cfp = self._cfp()
        valid = self._proposal(cfp, "resource-valid")
        invalid = self._proposal(cfp, "resource-invalid")
        invalid.payload["bid"]["energy_cost"] = -1.0
        late = self._proposal(cfp, "resource-late", created_at=36.0)

        selection = select_best_proposal(cfp, (valid, valid, invalid, late))

        self.assertEqual(selection.winner_bid.resource_id, "resource-valid")
        self.assertEqual(
            tuple(proposal.message_id for proposal in selection.valid_proposals),
            (valid.message_id,),
        )


if __name__ == "__main__":
    unittest.main()

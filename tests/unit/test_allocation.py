import unittest
from concurrent.futures import ThreadPoolExecutor

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
    AllocationOutcome,
    LocalResourceReservation,
    MissionRegistry,
    ReservationStatus,
    build_accept_message,
    build_cfp_message,
    build_reservation_status_message,
    evaluate_cfp,
    reservation_status_matches_accept,
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

    def test_evaluate_cfp_accepts_at_inclusive_deadline(self):
        response = evaluate_cfp(
            self._cfp(deadline=25.0),
            self._resource(),
            ("mobile_verification",),
            current_time=25.0,
            minimum_autonomy_percent=20.0,
            eta_seconds=4.0,
            energy_cost_percent=10.0,
            load=0.25,
        )

        self.assertIs(response.message_type, MessageType.PROPOSAL)


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

    def test_selection_accepts_at_deadline_and_rejects_after_deadline(self):
        cfp = self._cfp(deadline=35.0)
        at_deadline = self._proposal(
            cfp, "resource-at-deadline", created_at=35.0
        )
        after_deadline = self._proposal(
            cfp, "resource-after-deadline", created_at=35.0001
        )

        selection = select_best_proposal(cfp, (after_deadline, at_deadline))

        self.assertEqual(
            selection.winner_bid.resource_id, "resource-at-deadline"
        )
        self.assertEqual(
            tuple(proposal.message_id for proposal in selection.valid_proposals),
            (at_deadline.message_id,),
        )

    def test_reserves_available_resource_and_associates_mission(self):
        reservation = LocalResourceReservation(self._resource())

        result = reservation.reserve("mission-1", resource_id="drone-1")

        self.assertEqual(result.status, ReservationStatus.RESERVED)
        self.assertTrue(result.confirmed)
        self.assertEqual(result.mission_id, "mission-1")
        self.assertEqual(result.resource_state.status, ResourceStatus.RESERVED)
        self.assertFalse(result.resource_state.available)
        self.assertEqual(reservation.reserved_mission_id, "mission-1")

    def test_repeated_reservation_for_same_mission_is_idempotent(self):
        reservation = LocalResourceReservation(self._resource())
        first = reservation.reserve("mission-1")

        second = reservation.reserve("mission-1")

        self.assertEqual(first.status, ReservationStatus.RESERVED)
        self.assertEqual(second.status, ReservationStatus.ALREADY_RESERVED)
        self.assertTrue(second.confirmed)
        self.assertEqual(second.mission_id, "mission-1")

    def test_different_mission_cannot_use_reserved_resource(self):
        reservation = LocalResourceReservation(self._resource())
        reservation.reserve("mission-1")

        result = reservation.reserve("mission-2")

        self.assertEqual(result.status, ReservationStatus.RESOURCE_OCCUPIED)
        self.assertFalse(result.confirmed)
        self.assertEqual(result.mission_id, "mission-1")
        self.assertEqual(reservation.reserved_mission_id, "mission-1")

    def test_concurrent_missions_only_one_can_reserve(self):
        reservation = LocalResourceReservation(self._resource())

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(reservation.reserve, ("mission-a", "mission-b"))
            )

        statuses = {result.status for result in results}
        self.assertEqual(statuses, {
            ReservationStatus.RESERVED,
            ReservationStatus.RESOURCE_OCCUPIED,
        })
        self.assertIn(reservation.reserved_mission_id, {"mission-a", "mission-b"})
        self.assertEqual(reservation.resource_state.status, ResourceStatus.RESERVED)

    def test_unavailable_resource_returns_explicit_occupied_result(self):
        reservation = LocalResourceReservation(
            self._resource(available=False, status=ResourceStatus.UNAVAILABLE)
        )

        result = reservation.reserve("mission-1")

        self.assertEqual(result.status, ReservationStatus.RESOURCE_OCCUPIED)
        self.assertEqual(result.reason, "resource_not_available")
        self.assertIsNone(reservation.reserved_mission_id)

    def test_invalid_identifiers_do_not_change_resource(self):
        reservation = LocalResourceReservation(self._resource())

        empty_mission = reservation.reserve("")
        wrong_resource = reservation.reserve("mission-1", resource_id="other")

        self.assertEqual(empty_mission.status, ReservationStatus.INVALID_REQUEST)
        self.assertEqual(empty_mission.reason, "mission_id_invalid")
        self.assertEqual(wrong_resource.status, ReservationStatus.INVALID_REQUEST)
        self.assertEqual(wrong_resource.reason, "resource_id_invalid")
        self.assertEqual(reservation.resource_state.status, ResourceStatus.AVAILABLE)
        self.assertIsNone(reservation.reserved_mission_id)

    def test_accept_and_reservation_confirmation_preserve_correlations(self):
        cfp = self._cfp()
        proposal = self._proposal(cfp, "drone-1")
        accept = build_accept_message(cfp, proposal, 22.0, source_id="initiator-1")
        result = LocalResourceReservation(self._resource()).reserve(
            cfp.mission_id, resource_id="drone-1"
        )
        status = build_reservation_status_message(
            accept, result, resource_id="drone-1", created_at=22.0
        )

        self.assertEqual(accept.mission_id, cfp.mission_id)
        self.assertEqual(accept.incident_id, cfp.incident_id)
        self.assertEqual(accept.conversation_id, cfp.conversation_id)
        self.assertEqual(accept.payload["cfp_message_id"], cfp.message_id)
        self.assertEqual(accept.payload["proposal_message_id"], proposal.message_id)
        restored = Message.from_json(status.to_json())
        self.assertTrue(reservation_status_matches_accept(restored, accept, "drone-1"))
        self.assertEqual(restored.payload["status"], "reserved")

    def test_reservation_status_rejects_contradictory_confirmation(self):
        cfp = self._cfp()
        proposal = self._proposal(cfp, "drone-1")
        accept = build_accept_message(cfp, proposal, 22.0)
        reservation = LocalResourceReservation(self._resource())
        result = reservation.reserve(cfp.mission_id, resource_id="drone-1")
        status = build_reservation_status_message(
            accept, result, resource_id="drone-1", created_at=22.0
        )

        status.payload["reservation_status"] = ReservationStatus.RESOURCE_OCCUPIED
        self.assertFalse(
            reservation_status_matches_accept(status, accept, "drone-1")
        )

        status.payload.pop("reservation_status")
        self.assertFalse(
            reservation_status_matches_accept(status, accept, "drone-1")
        )

    def test_reservation_status_accepts_already_reserved_and_valid_failure(self):
        cfp = self._cfp()
        proposal = self._proposal(cfp, "drone-1")
        accept = build_accept_message(cfp, proposal, 22.0)
        reservation = LocalResourceReservation(self._resource())
        reservation.reserve(cfp.mission_id, resource_id="drone-1")
        already_reserved = reservation.reserve(cfp.mission_id, resource_id="drone-1")
        confirmed = build_reservation_status_message(
            accept, already_reserved, resource_id="drone-1", created_at=22.0
        )
        self.assertTrue(
            reservation_status_matches_accept(confirmed, accept, "drone-1")
        )

        occupied = LocalResourceReservation(
            self._resource(available=False, status=ResourceStatus.UNAVAILABLE)
        ).reserve(cfp.mission_id, resource_id="drone-1")
        failed = build_reservation_status_message(
            accept, occupied, resource_id="drone-1", created_at=22.0
        )
        self.assertTrue(reservation_status_matches_accept(failed, accept, "drone-1"))

    def test_accept_rejects_proposal_from_another_conversation(self):
        cfp = self._cfp()
        proposal = self._proposal(cfp, "drone-1", conversation_id="other")

        with self.assertRaises(ValueError):
            build_accept_message(cfp, proposal, 22.0)

    def test_allocation_outcomes_are_distinct_and_failure_is_not_confirmation(self):
        self.assertEqual(
            {
                AllocationOutcome.RESERVATION_CONFIRMED,
                AllocationOutcome.NO_ELIGIBLE_PROPOSALS,
                AllocationOutcome.RESERVATION_REJECTED,
                AllocationOutcome.CONFIRMATION_UNKNOWN,
            },
            {
                "reservation_confirmed",
                "no_eligible_proposals",
                "reservation_rejected",
                "confirmation_unknown",
            },
        )
        cfp = self._cfp()
        proposal = self._proposal(cfp, "drone-1")
        accept = build_accept_message(cfp, proposal, 22.0)
        result = LocalResourceReservation(
            self._resource(available=False, status=ResourceStatus.UNAVAILABLE)
        ).reserve(cfp.mission_id)
        status = build_reservation_status_message(
            accept, result, resource_id="drone-1", created_at=22.0
        )

        self.assertEqual(status.payload["status"], "reservation_failed")
        self.assertEqual(status.payload["reservation_status"], ReservationStatus.RESOURCE_OCCUPIED)
        self.assertNotEqual(status.payload["status"], "reserved")

    def test_two_unavailable_resources_leave_mission_unreserved(self):
        mission = self.registry.create_from_decision(
            self.incident, {"decision": "request_mobile_verification"}
        )
        cfp = build_cfp_message(mission, 20.0, 35.0, message_id="cfp-1", conversation_id="conversation-1")
        responses = tuple(
            evaluate_cfp(
                cfp,
                ResourceState(
                    resource_id,
                    "drone",
                    Position(1, 2),
                    False,
                    80.0,
                    ResourceStatus.UNAVAILABLE,
                ),
                ("mobile_verification",),
                current_time=21.0,
                minimum_autonomy_percent=20.0,
                eta_seconds=4.0,
                energy_cost_percent=10.0,
                load=0.25,
            )
            for resource_id in ("drone-a", "drone-b")
        )

        selection = select_best_proposal(cfp, responses)

        self.assertIsNone(selection.winner)
        self.assertEqual(selection.reason, "no_valid_proposals")
        self.assertEqual(mission.status, MissionStatus.PROPOSED)

    def test_explicit_reservation_failure_can_be_followed_by_new_cfp(self):
        mission = self.registry.create_from_decision(
            self.incident, {"decision": "request_mobile_verification"}
        )
        first_cfp = build_cfp_message(
            mission, 20.0, 35.0, message_id="cfp-1", conversation_id="conversation-1"
        )
        first_proposal = self._proposal(first_cfp, "drone-a")
        first_accept = build_accept_message(first_cfp, first_proposal, 22.0)
        failed_result = LocalResourceReservation(
            self._resource(available=False, status=ResourceStatus.UNAVAILABLE)
        ).reserve(first_cfp.mission_id)
        failed_status = build_reservation_status_message(
            first_accept, failed_result, resource_id="drone-a", created_at=22.0
        )

        second_cfp = build_cfp_message(
            mission,
            created_at=23.0,
            deadline=35.0,
        )
        second_proposal = self._proposal(second_cfp, "drone-b")
        second_accept = build_accept_message(second_cfp, second_proposal, 24.0)
        confirmed_result = LocalResourceReservation(
            ResourceState("drone-b", "drone", Position(1, 2), True, 80.0)
        ).reserve(second_cfp.mission_id)
        confirmed_status = build_reservation_status_message(
            second_accept, confirmed_result, resource_id="drone-b", created_at=24.0
        )

        self.assertEqual(failed_status.payload["status"], "reservation_failed")
        self.assertEqual(confirmed_status.payload["status"], "reserved")
        self.assertNotEqual(first_cfp.message_id, second_cfp.message_id)
        self.assertNotEqual(first_cfp.conversation_id, second_cfp.conversation_id)
        self.assertEqual(first_cfp.mission_id, second_cfp.mission_id)
        self.assertEqual(first_cfp.incident_id, second_cfp.incident_id)

    def test_late_proposal_from_previous_round_is_not_valid_for_new_cfp(self):
        mission = self.registry.create_from_decision(
            self.incident, {"decision": "request_mobile_verification"}
        )
        first_cfp = build_cfp_message(
            mission, 20.0, 35.0, message_id="cfp-1", conversation_id="conversation-1"
        )
        late_proposal = self._proposal(first_cfp, "drone-a", created_at=34.0)
        second_cfp = build_cfp_message(
            mission, 23.0, 35.0
        )

        selection = select_best_proposal(second_cfp, (late_proposal,))

        self.assertIsNone(selection.winner)
        self.assertEqual(selection.reason, "no_valid_proposals")


if __name__ == "__main__":
    unittest.main()

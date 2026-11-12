"""Chronology regressions for CFP, proposal and acceptance messages."""

import unittest

from isia.communication.messages import Message, MessageType, model_to_dict
from isia.domain.models import Bid, Mission, Position, ResourceState
from isia.reasoning.allocation import (
    accept_matches_proposal,
    build_accept_message,
    build_cfp_message,
    evaluate_cfp,
    select_best_proposal,
)


class TestContractNetChronology(unittest.TestCase):
    def setUp(self):
        self.mission = Mission(
            "mission-1", "incident-1", "verify_incident", Position(3, 4),
            "mobile_verification", 0,
        )
        self.cfp = build_cfp_message(
            self.mission, 10.0, 20.0,
            message_id="cfp-1", conversation_id="conversation-1",
        )
        self.resource = ResourceState(
            "drone-1", "drone", Position(0, 0), True, 100.0,
        )

    def proposal(self, created_at):
        bid = Bid(self.mission.mission_id, self.resource.resource_id, 5.0, 2.0, 0.0)
        return Message(
            f"proposal-{created_at}", MessageType.PROPOSAL, created_at,
            {"cfp_message_id": self.cfp.message_id, "bid": model_to_dict(bid)},
            mission_id=self.mission.mission_id,
            incident_id=self.mission.incident_id,
            source_id=self.resource.resource_id,
            conversation_id=self.cfp.conversation_id,
        )

    def accept(self, proposal, created_at):
        # Build an incoming message independently of the production builder.
        return Message(
            "accept-1", MessageType.ACCEPT, created_at,
            {
                "cfp_message_id": self.cfp.message_id,
                "proposal_message_id": proposal.message_id,
                "resource_id": self.resource.resource_id,
            },
            mission_id=self.mission.mission_id,
            incident_id=self.mission.incident_id,
            conversation_id=self.cfp.conversation_id,
        )

    def test_evaluation_cannot_emit_a_response_before_the_cfp(self):
        with self.assertRaises(ValueError):
            evaluate_cfp(
                self.cfp, self.resource, ("mobile_verification",),
                current_time=9.0, minimum_autonomy_percent=10.0,
                eta_seconds=5.0, energy_cost_percent=2.0, load=0.0,
            )

    def test_accept_builder_rejects_proposal_before_cfp(self):
        with self.assertRaises(ValueError):
            build_accept_message(self.cfp, self.proposal(9.0), 15.0)

    def test_accept_builder_rejects_proposal_after_deadline(self):
        with self.assertRaises(ValueError):
            build_accept_message(self.cfp, self.proposal(21.0), 22.0)

    def test_accept_builder_rejects_acceptance_before_proposal(self):
        with self.assertRaises(ValueError):
            build_accept_message(self.cfp, self.proposal(15.0), 14.0)

    def test_incoming_acceptance_rejects_invalid_chronology(self):
        for proposal_time, accept_time in ((9.0, 15.0), (21.0, 22.0), (15.0, 14.0)):
            with self.subTest(proposal_time=proposal_time, accept_time=accept_time):
                proposal = self.proposal(proposal_time)
                self.assertFalse(accept_matches_proposal(
                    self.accept(proposal, accept_time), self.cfp, proposal,
                    self.resource.resource_id,
                ))

    def test_equal_emission_times_are_valid(self):
        proposal = self.proposal(10.0)
        accept = build_accept_message(self.cfp, proposal, 10.0)
        self.assertTrue(accept_matches_proposal(
            accept, self.cfp, proposal, self.resource.resource_id,
        ))

    def test_deadline_is_inclusive_and_does_not_limit_acceptance(self):
        proposal = self.proposal(20.0)
        accept = build_accept_message(self.cfp, proposal, 25.0)
        self.assertTrue(accept_matches_proposal(
            accept, self.cfp, proposal, self.resource.resource_id,
        ))
        selection = select_best_proposal(
            self.cfp, (self.proposal(9.0), proposal, self.proposal(21.0)),
        )
        self.assertIs(selection.winner, proposal)
        self.assertEqual(selection.valid_proposals, (proposal,))


if __name__ == "__main__":
    unittest.main()

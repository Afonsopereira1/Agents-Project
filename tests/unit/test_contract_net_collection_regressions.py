"""Regressões da recolha Contract Net com a fila real dos comportamentos SPADE."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from isia.communication.messages import Message, MessageType
from isia.domain.models import Mission, MissionStatus, Position, ResourceState

try:
    from contract_net_demo import ContractNetInitiatorAgent
    from isia.communication.transport import (
        CONTRACT_NET_PROTOCOL,
        PERFORMATIVE_INFORM,
        PERFORMATIVE_PROPOSE,
        PERFORMATIVE_REJECT_PROPOSAL,
        build_spade_message,
        parse_spade_message,
    )
    from isia.reasoning.allocation import (
        AllocationOutcome,
        LocalResourceReservation,
        build_reservation_status_message,
    )
except ImportError:
    ContractNetInitiatorAgent = None


@unittest.skipUnless(ContractNetInitiatorAgent is not None, "SPADE não está instalado")
class TestContractNetCollectionRegressions(unittest.IsolatedAsyncioTestCase):
    def prepare(self, *, receive_timeout=1.0):
        self.agent = ContractNetInitiatorAgent(
            "initiator@localhost", "local-test",
            Mission(
                "mission-1", "incident-1", "verify_incident", Position(3, 4),
                "mobile_verification", 0,
            ),
            {"drone@localhost": "drone-1"},
            simulated_time=20.0, deadline=35.0,
            receive_timeout=receive_timeout,
        )
        self.behaviour = self.agent.ContractNetBehaviour()
        self.behaviour.set_agent(self.agent)
        self.reservation = LocalResourceReservation(
            ResourceState("drone-1", "drone", Position(0, 0), True, 80.0)
        )
        self.sent = []
        self.responses_for_cfp = lambda cfp: ()

        async def send(outgoing):
            body = parse_spade_message(
                outgoing, expected_protocol=CONTRACT_NET_PROTOCOL,
            )
            self.sent.append(body)
            if body.message_type is MessageType.CFP:
                for incoming in self.responses_for_cfp(body):
                    self.behaviour.queue.put_nowait(incoming)
            elif body.message_type is MessageType.ACCEPT:
                result = self.reservation.reserve(
                    body.mission_id, resource_id=body.payload["resource_id"],
                )
                status = build_reservation_status_message(
                    body, result, resource_id="drone-1",
                    created_at=body.created_at,
                )
                self.behaviour.queue.put_nowait(self.wire(status))

        self.behaviour.send = send

    def proposal(self, cfp, *, message_id="valid-proposal", created_at=21.0):
        return Message(
            message_id, MessageType.PROPOSAL, created_at,
            {
                "cfp_message_id": cfp.message_id,
                "bid": {
                    "mission_id": cfp.mission_id, "resource_id": "drone-1",
                    "eta": 4.0, "energy_cost": 2.0, "load": 0.0,
                },
            },
            mission_id=cfp.mission_id, incident_id=cfp.incident_id,
            source_id="drone-1", conversation_id=cfp.conversation_id,
        )

    def wire(self, body, *, sender="drone@localhost"):
        performative = {
            MessageType.PROPOSAL: PERFORMATIVE_PROPOSE,
            MessageType.REJECT: PERFORMATIVE_REJECT_PROPOSAL,
            MessageType.STATUS: PERFORMATIVE_INFORM,
        }[body.message_type]
        incoming = build_spade_message(
            "initiator@localhost", body, performative=performative,
            conversation_id=body.conversation_id,
            in_reply_to=body.payload.get("accept_message_id", body.payload.get("cfp_message_id")),
            protocol=CONTRACT_NET_PROTOCOL,
        )
        incoming.sender = sender
        return incoming

    async def test_invalid_proposal_does_not_hide_valid_proposal_in_real_queue(self):
        for defect in (
            "missing_bid", "malformed_bid", "bid_mission", "bid_resource",
            "negative_eta", "before_cfp", "after_deadline", "wrong_cfp",
        ):
            for same_message_id in (False, True):
                with self.subTest(defect=defect, same_message_id=same_message_id):
                    self.prepare()
                    valid_proposals = []

                    def responses(cfp):
                        valid = self.proposal(cfp)
                        valid_proposals.append(valid)
                        invalid = self.proposal(
                            cfp,
                            message_id=valid.message_id if same_message_id else "invalid-proposal",
                            created_at=(
                                19.0 if defect == "before_cfp"
                                else 35.1 if defect == "after_deadline" else 21.0
                            ),
                        )
                        if defect == "missing_bid":
                            invalid.payload.pop("bid")
                        elif defect == "malformed_bid":
                            invalid.payload["bid"] = {}
                        elif defect == "bid_mission":
                            invalid.payload["bid"]["mission_id"] = "another-mission"
                        elif defect == "bid_resource":
                            invalid.payload["bid"]["resource_id"] = "another-resource"
                        elif defect == "negative_eta":
                            invalid.payload["bid"]["eta"] = -1.0
                        elif defect == "wrong_cfp":
                            invalid.payload["cfp_message_id"] = "another-cfp"
                        return self.wire(invalid), self.wire(valid)

                    self.responses_for_cfp = responses
                    await self.behaviour.run()

                    self.assertEqual(
                        self.agent.result.outcome, AllocationOutcome.RESERVATION_CONFIRMED,
                    )
                    self.assertEqual(self.agent.mission.status, MissionStatus.RESERVED)
                    self.assertEqual(self.reservation.reserved_mission_id, "mission-1")
                    self.assertEqual(
                        self.agent.selection.winner.to_dict(), valid_proposals[0].to_dict(),
                    )
                    accepts = [m for m in self.sent if m.message_type is MessageType.ACCEPT]
                    self.assertEqual(len(accepts), 1)
                    self.assertEqual(accepts[0].payload["proposal_message_id"], "valid-proposal")
                    self.assertEqual(self.agent.confirmation.payload["status"], "reserved")
                    self.assertTrue(self.behaviour.queue.empty())

    async def test_proposal_at_inclusive_deadline_can_be_reserved(self):
        self.prepare()
        self.responses_for_cfp = lambda cfp: (
            self.wire(self.proposal(cfp, created_at=cfp.payload["deadline"])),
        )

        await self.behaviour.run()

        self.assertEqual(self.agent.result.outcome, AllocationOutcome.RESERVATION_CONFIRMED)
        self.assertEqual(self.agent.accept.created_at, 35.0)

    async def test_rejection_after_cfp_deadline_remains_a_valid_response(self):
        self.prepare()

        def responses(cfp):
            rejection = Message(
                "reject-expired", MessageType.REJECT, 36.0,
                {"cfp_message_id": cfp.message_id, "reason": "cfp_expired"},
                mission_id=cfp.mission_id, incident_id=cfp.incident_id,
                source_id="drone-1", conversation_id=cfp.conversation_id,
            )
            return (self.wire(rejection),)

        self.responses_for_cfp = responses
        await self.behaviour.run()

        self.assertEqual(self.agent.result.outcome, AllocationOutcome.NO_ELIGIBLE_PROPOSALS)
        self.assertEqual(self.agent.responses["drone@localhost"].message_type, MessageType.REJECT)
        self.assertEqual([m.message_type for m in self.sent], [MessageType.CFP])
        self.assertIsNone(self.reservation.reserved_mission_id)

    async def test_no_response_still_times_out_without_accept(self):
        self.prepare(receive_timeout=0.01)

        await self.behaviour.run()

        self.assertEqual(self.agent.result.outcome, AllocationOutcome.NO_ELIGIBLE_PROPOSALS)
        self.assertEqual(self.agent.responses, {})
        self.assertEqual([m.message_type for m in self.sent], [MessageType.CFP])
        self.assertIsNone(self.reservation.reserved_mission_id)

    async def test_invalid_responses_do_not_renew_timeout_or_admit_late_proposal(self):
        self.prepare()
        self.responses_for_cfp = lambda cfp: (
            self.wire(self.proposal(cfp, message_id="foreign-1"), sender="other@localhost"),
            self.wire(self.proposal(cfp, message_id="foreign-2"), sender="other@localhost"),
            self.wire(self.proposal(cfp)),
        )
        now = [100.0]
        timeouts = []
        real_receive = self.behaviour.receive

        async def receive(timeout):
            timeouts.append(timeout)
            incoming = await real_receive(timeout=timeout)
            now[0] += 0.4
            return incoming

        self.behaviour.receive = receive
        with patch("contract_net_demo.time", SimpleNamespace(monotonic=lambda: now[0])):
            await self.behaviour.run()

        self.assertEqual(self.agent.result.outcome, AllocationOutcome.NO_ELIGIBLE_PROPOSALS)
        self.assertEqual(self.agent.responses, {})
        self.assertEqual([m.message_type for m in self.sent], [MessageType.CFP])
        self.assertEqual(len(timeouts), 3)
        for actual, expected in zip(timeouts, (1.0, 0.6, 0.2)):
            self.assertAlmostEqual(actual, expected)

    async def test_confirmation_at_real_timeout_remains_unknown_without_new_round(self):
        self.prepare()
        self.responses_for_cfp = lambda cfp: (self.wire(self.proposal(cfp)),)
        now = [100.0]
        real_receive = self.behaviour.receive

        async def receive(timeout):
            incoming = await real_receive(timeout=timeout)
            if incoming.get_metadata("performative") == PERFORMATIVE_INFORM:
                now[0] += 1.0
            return incoming

        self.behaviour.receive = receive
        with patch("contract_net_demo.time", SimpleNamespace(monotonic=lambda: now[0])):
            await self.behaviour.run()

        self.assertEqual(self.agent.result.outcome, AllocationOutcome.CONFIRMATION_UNKNOWN)
        self.assertEqual(self.agent.mission.status, MissionStatus.PROPOSED)
        self.assertIsNone(self.agent.confirmation)
        self.assertEqual(len(self.agent.round_history), 1)
        self.assertEqual(
            [m.message_type for m in self.sent], [MessageType.CFP, MessageType.ACCEPT],
        )


if __name__ == "__main__":
    unittest.main()

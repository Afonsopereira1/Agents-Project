import unittest
from unittest.mock import AsyncMock

from isia.communication.messages import Message
from isia.communication.transport import (
    CONTRACT_NET_PROTOCOL,
    PERFORMATIVE_ACCEPT_PROPOSAL,
    PERFORMATIVE_CFP,
    PERFORMATIVE_REJECT_PROPOSAL,
    build_spade_message,
    parse_spade_message,
)
from isia.domain.models import Mission, Position, ResourceState
from isia.reasoning.allocation import (
    build_accept_message,
    build_cfp_message,
    build_proposal_rejection_message,
)

try:
    from isia.agents.mobile import MobileResourceAgent
except ImportError:
    MobileResourceAgent = None


@unittest.skipUnless(MobileResourceAgent is not None, "SPADE não está instalado")
class TestMobileProposalLifecycle(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.agent = MobileResourceAgent(
            "drone@localhost", "local-test",
            ResourceState("drone-1", "drone", Position(1, 2), True, 80.0),
            ("mobile_verification",),
            minimum_autonomy_percent=20.0, eta_seconds=4.0,
            energy_cost_percent=10.0, load=0.25, simulated_time=21.0,
        )
        self.mission = Mission(
            "mission-1", "incident-1", "verify_incident", Position(6, 9),
            "mobile_verification", 2,
        )
        self.cfp = build_cfp_message(
            self.mission, 20.0, 25.0,
            message_id="cfp-1", conversation_id="conversation-1",
        )

    async def dispatch(self, body, *, sender="initiator@localhost", metadata=None):
        if body.message_type.value == "CFP":
            behaviour = MobileResourceAgent.ContractNetBehaviour()
            performative = PERFORMATIVE_CFP
            reply_to = None
        else:
            behaviour = MobileResourceAgent.AcceptBehaviour()
            performative = (
                PERFORMATIVE_REJECT_PROPOSAL
                if body.message_type.value == "REJECT"
                else PERFORMATIVE_ACCEPT_PROPOSAL
            )
            reply_to = body.payload.get("proposal_message_id")
        behaviour.set_agent(self.agent)
        incoming = build_spade_message(
            str(self.agent.jid), body, performative=performative,
            conversation_id=body.conversation_id, in_reply_to=reply_to,
            protocol=CONTRACT_NET_PROTOCOL,
        )
        incoming.sender = sender
        for key, value in (metadata or {}).items():
            incoming.set_metadata(key, value)
        behaviour.receive = AsyncMock(return_value=incoming)
        behaviour.send = AsyncMock()
        await behaviour.run()
        return [
            parse_spade_message(call.args[0], expected_protocol=CONTRACT_NET_PROTOCOL)
            for call in behaviour.send.await_args_list
        ]

    async def propose(self, cfp=None):
        responses = await self.dispatch(cfp or self.cfp)
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0].message_type.value, "PROPOSAL")
        return responses[0]

    async def test_reject_invalidates_proposal_and_late_accept_cannot_reserve(self):
        proposal = await self.propose()
        rejection = build_proposal_rejection_message(self.cfp, proposal, 21.0)
        self.assertEqual(await self.dispatch(rejection), [])
        self.assertNotIn(proposal.message_id, self.agent._proposal_context)
        responses = await self.dispatch(build_accept_message(self.cfp, proposal, 21.0))
        self.assertEqual(responses[0].payload["status"], "reservation_failed")
        self.assertTrue(self.agent.resource.available)

    async def test_foreign_or_uncorrelated_reject_does_not_invalidate(self):
        proposal = await self.propose()
        rejection = build_proposal_rejection_message(self.cfp, proposal, 21.0)
        await self.dispatch(rejection, sender="other@localhost")
        self.assertIn(proposal.message_id, self.agent._proposal_context)
        await self.dispatch(rejection, metadata={"in-reply-to": "another-proposal"})
        self.assertIn(proposal.message_id, self.agent._proposal_context)
        data = rejection.to_dict()
        data["mission_id"] = "another-mission"
        await self.dispatch(Message.from_dict(data))
        self.assertIn(proposal.message_id, self.agent._proposal_context)

    async def test_expired_proposal_cannot_reserve(self):
        proposal = await self.propose()
        self.agent.set_simulated_time(36.0)
        responses = await self.dispatch(build_accept_message(self.cfp, proposal, 36.0))
        self.assertEqual(responses[0].payload["status"], "reservation_failed")
        self.assertTrue(self.agent.resource.available)
        self.assertNotIn(proposal.message_id, self.agent._proposal_context)

    async def test_accept_at_local_expiry_is_valid_after_cfp_deadline(self):
        proposal = await self.propose()
        self.agent.set_simulated_time(35.0)
        responses = await self.dispatch(build_accept_message(self.cfp, proposal, 35.0))
        self.assertEqual(responses[0].payload["status"], "reserved")

    async def test_new_round_invalidates_previous_proposal(self):
        old_proposal = await self.propose()
        self.agent.set_simulated_time(22.0)
        new_cfp = build_cfp_message(
            self.mission, 22.0, 27.0,
            message_id="cfp-2", conversation_id="conversation-2",
        )
        new_proposal = await self.propose(new_cfp)
        old_status = await self.dispatch(build_accept_message(self.cfp, old_proposal, 22.0))
        self.assertEqual(old_status[0].payload["status"], "reservation_failed")
        self.assertTrue(self.agent.resource.available)
        new_status = await self.dispatch(build_accept_message(new_cfp, new_proposal, 22.0))
        self.assertEqual(new_status[0].payload["status"], "reserved")

    async def test_old_cfp_replay_cannot_reopen_superseded_round(self):
        await self.propose()
        self.agent.set_simulated_time(22.0)
        new_cfp = build_cfp_message(self.mission, 22.0, 27.0)
        proposal = await self.propose(new_cfp)
        await self.dispatch(self.cfp)
        self.assertEqual(set(self.agent._proposal_context), {proposal.message_id})

    async def test_rejected_cfp_replay_cannot_reopen_proposal(self):
        proposal = await self.propose()
        await self.dispatch(build_proposal_rejection_message(self.cfp, proposal, 21.0))
        await self.dispatch(self.cfp)
        self.assertEqual(self.agent._proposal_context, {})

    async def test_duplicate_cfp_reuses_original_proposal(self):
        first = await self.propose()
        second = await self.propose()
        self.assertEqual(second.to_dict(), first.to_dict())
        self.assertEqual(set(self.agent._proposal_context), {first.message_id})

    async def test_changed_cfp_replay_cannot_extend_proposal_validity(self):
        proposal = await self.propose()
        changed = self.cfp.to_dict()
        changed["payload"] = {**changed["payload"], "deadline": 100.0}
        await self.dispatch(Message.from_dict(changed))
        self.agent.set_simulated_time(36.0)
        responses = await self.dispatch(build_accept_message(self.cfp, proposal, 36.0))
        self.assertEqual(responses[0].payload["status"], "reservation_failed")
        self.assertTrue(self.agent.resource.available)

    async def test_failed_proposal_send_allows_cfp_retry_without_stale_context(self):
        behaviour = MobileResourceAgent.ContractNetBehaviour()
        behaviour.set_agent(self.agent)
        incoming = build_spade_message(
            str(self.agent.jid), self.cfp, performative=PERFORMATIVE_CFP,
            conversation_id=self.cfp.conversation_id, protocol=CONTRACT_NET_PROTOCOL,
        )
        incoming.sender = "initiator@localhost"
        behaviour.receive = AsyncMock(return_value=incoming)
        behaviour.send = AsyncMock(side_effect=OSError("test transport failure"))
        with self.assertLogs("isia.agents.mobile", level="WARNING"):
            await behaviour.run()
        self.assertEqual(self.agent._proposal_context, {})
        proposal = await self.propose()
        self.assertIn(proposal.message_id, self.agent._proposal_context)

    async def test_repeated_accept_preserves_confirmed_reservation_after_expiry(self):
        proposal = await self.propose()
        accept = build_accept_message(self.cfp, proposal, 21.0)
        first = await self.dispatch(accept)
        self.assertEqual(first[0].payload["status"], "reserved")
        self.agent.set_simulated_time(36.0)
        repeated = await self.dispatch(accept)
        self.assertEqual(repeated[0].payload["status"], "reserved")
        self.assertEqual(repeated[0].payload["reservation_status"], "already_reserved")

    async def test_future_accept_does_not_reserve_before_its_emission(self):
        proposal = await self.propose()
        responses = await self.dispatch(build_accept_message(self.cfp, proposal, 22.0))
        self.assertEqual(responses[0].payload["status"], "reservation_failed")
        self.assertTrue(self.agent.resource.available)

    async def test_uncorrelated_accept_metadata_does_not_reserve(self):
        proposal = await self.propose()
        responses = await self.dispatch(
            build_accept_message(self.cfp, proposal, 21.0),
            metadata={"in-reply-to": "another-proposal"},
        )
        self.assertEqual(responses[0].payload["status"], "reservation_failed")
        self.assertTrue(self.agent.resource.available)

    async def test_reject_template_routes_to_decision_behaviour(self):
        proposal = await self.propose()
        rejection = build_proposal_rejection_message(self.cfp, proposal, 21.0)
        incoming = build_spade_message(
            str(self.agent.jid), rejection,
            performative=PERFORMATIVE_REJECT_PROPOSAL,
            conversation_id=rejection.conversation_id,
            in_reply_to=proposal.message_id, protocol=CONTRACT_NET_PROTOCOL,
        )
        await self.agent.setup()
        decision = next(
            behaviour for behaviour in self.agent.behaviours
            if isinstance(behaviour, MobileResourceAgent.AcceptBehaviour)
        )
        self.assertTrue(decision.template.match(incoming))

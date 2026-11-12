import unittest
from unittest.mock import AsyncMock

from isia.communication.messages import Message, MessageType
from isia.communication.transport import (
    CONTRACT_NET_PROTOCOL,
    PERFORMATIVE_ACCEPT_PROPOSAL,
    PERFORMATIVE_CFP,
    PERFORMATIVE_PROPOSE,
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


_MATCHING_PERFORMATIVE = object()


@unittest.skipUnless(MobileResourceAgent is not None, "SPADE não está instalado")
class TestMobileRoundRegressions(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.agent = self.make_agent()

    def make_agent(self):
        return MobileResourceAgent(
            "drone@localhost", "local-test",
            ResourceState("drone-1", "drone", Position(1, 2), True, 80.0),
            ("mobile_verification",),
            minimum_autonomy_percent=20.0, eta_seconds=4.0,
            energy_cost_percent=10.0, load=0.25, simulated_time=21.0,
        )

    def cfp(self, message_id, *, round_number=None, mission_id="mission-1"):
        mission = Mission(
            mission_id, "incident-1", "verify_incident", Position(6, 9),
            "mobile_verification", 2,
        )
        cfp = build_cfp_message(
            mission, 20.0, 25.0, message_id=message_id,
            conversation_id=f"conversation-{message_id}",
        )
        if round_number is None:
            return cfp
        data = cfp.to_dict()
        data["payload"] = {**data["payload"], "round_number": round_number}
        return Message.from_dict(data)

    async def dispatch(
        self, body, *, agent=None, sender="initiator@localhost",
        performative=_MATCHING_PERFORMATIVE, send_error=None,
    ):
        agent = self.agent if agent is None else agent
        if body.message_type is MessageType.CFP:
            behaviour = MobileResourceAgent.ContractNetBehaviour()
            expected_performative = PERFORMATIVE_CFP
            reply_to = None
        else:
            behaviour = MobileResourceAgent.AcceptBehaviour()
            expected_performative = (
                PERFORMATIVE_REJECT_PROPOSAL
                if body.message_type is MessageType.REJECT
                else PERFORMATIVE_ACCEPT_PROPOSAL
            )
            reply_to = body.payload.get("proposal_message_id")
        behaviour.set_agent(agent)
        incoming = build_spade_message(
            str(agent.jid), body, performative=expected_performative,
            conversation_id=body.conversation_id, in_reply_to=reply_to,
            protocol=CONTRACT_NET_PROTOCOL,
        )
        incoming.sender = sender
        if performative is None:
            incoming._metadata.pop("performative")
        elif performative is not _MATCHING_PERFORMATIVE:
            incoming.set_metadata("performative", performative)
        behaviour.receive = AsyncMock(return_value=incoming)
        behaviour.send = AsyncMock(side_effect=send_error)
        await behaviour.run()
        return [
            parse_spade_message(call.args[0], expected_protocol=CONTRACT_NET_PROTOCOL)
            for call in behaviour.send.await_args_list
        ]

    async def propose(self, cfp, **kwargs):
        replies = await self.dispatch(cfp, **kwargs)
        self.assertEqual(len(replies), 1)
        self.assertIs(replies[0].message_type, MessageType.PROPOSAL)
        return replies[0]

    async def assert_reserved(self, cfp, proposal, **kwargs):
        replies = await self.dispatch(build_accept_message(cfp, proposal, 21.0), **kwargs)
        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0].payload["status"], "reserved")
        return replies[0]

    async def test_unseen_previous_round_at_equal_time_cannot_replace_current(self):
        current = self.cfp("current-cfp", round_number=2)
        proposal = await self.propose(current)
        previous = self.cfp("previous-cfp", round_number=1)

        self.assertEqual(await self.dispatch(previous), [])
        self.assertEqual(set(self.agent._proposal_context), {proposal.message_id})
        await self.assert_reserved(current, proposal)

    async def test_next_round_at_equal_time_supersedes_previous(self):
        first = self.cfp("first-cfp", round_number=1)
        previous = await self.propose(first)
        second = self.cfp("second-cfp", round_number=2)
        current = await self.propose(second)

        self.assertEqual(set(self.agent._proposal_context), {current.message_id})
        rejected = await self.dispatch(build_accept_message(first, previous, 21.0))
        self.assertEqual(rejected[0].payload["status"], "reservation_failed")
        self.assertTrue(self.agent.resource.available)
        await self.assert_reserved(second, current)

    async def test_round_order_does_not_depend_on_lexical_message_ids(self):
        for old_id, current_id in (("a-cfp", "z-cfp"), ("z-cfp", "a-cfp")):
            with self.subTest(old_id=old_id, current_id=current_id):
                agent = self.make_agent()
                current = self.cfp(current_id, round_number=2)
                proposal = await self.propose(current, agent=agent)
                old = self.cfp(old_id, round_number=1)

                self.assertEqual(await self.dispatch(old, agent=agent), [])
                self.assertEqual(set(agent._proposal_context), {proposal.message_id})
                await self.assert_reserved(current, proposal, agent=agent)

    async def test_different_cfp_id_cannot_reuse_current_round_number(self):
        current = self.cfp("original-cfp", round_number=2)
        proposal = await self.propose(current)
        conflicting = self.cfp("conflicting-cfp", round_number=2)

        self.assertEqual(await self.dispatch(conflicting), [])
        self.assertEqual(set(self.agent._proposal_context), {proposal.message_id})
        await self.assert_reserved(current, proposal)

    async def test_duplicate_numbered_cfp_reuses_the_same_proposal(self):
        cfp = self.cfp("numbered-cfp", round_number=2)
        first = await self.propose(cfp)
        repeated = await self.propose(cfp)

        self.assertEqual(repeated.to_dict(), first.to_dict())
        self.assertEqual(set(self.agent._proposal_context), {first.message_id})

    async def test_ambiguous_legacy_cfps_keep_both_proposals_acceptable(self):
        for accept_order in ((0, 1), (1, 0)):
            with self.subTest(accept_order=accept_order):
                agent = self.make_agent()
                cfps = (self.cfp("legacy-a"), self.cfp("legacy-b"))
                proposals = [await self.propose(cfp, agent=agent) for cfp in cfps]

                self.assertEqual(
                    set(agent._proposal_context), {proposal.message_id for proposal in proposals}
                )
                first, repeated = [
                    await self.assert_reserved(cfps[index], proposals[index], agent=agent)
                    for index in accept_order
                ]
                self.assertEqual(first.payload["reservation_status"], "reserved")
                self.assertEqual(repeated.payload["reservation_status"], "already_reserved")
                self.assertEqual(agent.reservation.reserved_mission_id, "mission-1")

    async def test_all_confirmed_legacy_proposals_remain_idempotent_after_expiry(self):
        cfps = (self.cfp("legacy-a"), self.cfp("legacy-b"))
        proposals = [await self.propose(cfp) for cfp in cfps]
        for cfp, proposal in zip(cfps, proposals):
            await self.assert_reserved(cfp, proposal)

        self.agent.set_simulated_time(36.0)
        for cfp, proposal in zip(cfps, proposals):
            reply = await self.assert_reserved(cfp, proposal)
            self.assertEqual(reply.payload["reservation_status"], "already_reserved")

    async def test_mixed_cfps_at_equal_time_preserve_both_confirmations(self):
        for incoming_order in ((0, 1), (1, 0)):
            with self.subTest(incoming_order=incoming_order):
                agent = self.make_agent()
                cfps = (
                    self.cfp("numbered-cfp", round_number=2),
                    self.cfp("legacy-cfp"),
                )
                proposals = {}
                for index in incoming_order:
                    proposals[index] = await self.propose(cfps[index], agent=agent)

                self.assertEqual(
                    set(agent._proposal_context),
                    {proposal.message_id for proposal in proposals.values()},
                )
                for index in incoming_order:
                    await self.assert_reserved(cfps[index], proposals[index], agent=agent)
                agent.set_simulated_time(36.0)
                for index in incoming_order:
                    reply = await self.assert_reserved(cfps[index], proposals[index], agent=agent)
                    self.assertEqual(reply.payload["reservation_status"], "already_reserved")

    async def test_round_high_water_survives_rejection_expiry_and_send_failure(self):
        for close_with in ("reject", "expire", "send_failure"):
            with self.subTest(close_with=close_with):
                agent = self.make_agent()
                current = self.cfp("current-cfp", round_number=2)
                if close_with == "send_failure":
                    with self.assertLogs("isia.agents.mobile", level="WARNING"):
                        await self.dispatch(
                            current, agent=agent, send_error=OSError("test transport failure"),
                        )
                else:
                    proposal = await self.propose(current, agent=agent)
                    if close_with == "reject":
                        await self.dispatch(
                            build_proposal_rejection_message(current, proposal, 21.0),
                            agent=agent,
                        )
                    else:
                        agent.set_simulated_time(36.0)
                self.assertEqual(agent._proposal_context, {})

                previous = self.cfp("unseen-previous-cfp", round_number=1)
                self.assertEqual(await self.dispatch(previous, agent=agent), [])
                self.assertEqual(agent._proposal_context, {})

    async def test_round_numbers_are_scoped_by_initiator(self):
        first = self.cfp("initiator-a-cfp", round_number=2)
        proposal_a = await self.propose(first, sender="initiator-a@localhost/device")
        second = self.cfp("initiator-b-cfp", round_number=1)
        proposal_b = await self.propose(second, sender="initiator-b@localhost/device")

        self.assertEqual(
            set(self.agent._proposal_context), {proposal_a.message_id, proposal_b.message_id}
        )
        await self.assert_reserved(second, proposal_b, sender="initiator-b@localhost/other")

    async def test_round_numbers_are_scoped_by_mission_and_do_not_double_reserve(self):
        first = self.cfp("mission-a-cfp", round_number=2, mission_id="mission-a")
        proposal_a = await self.propose(first)
        second = self.cfp("mission-b-cfp", round_number=1, mission_id="mission-b")
        proposal_b = await self.propose(second)

        self.assertEqual(
            set(self.agent._proposal_context), {proposal_a.message_id, proposal_b.message_id}
        )
        await self.assert_reserved(first, proposal_a)
        occupied = await self.dispatch(build_accept_message(second, proposal_b, 21.0))
        self.assertEqual(occupied[0].payload["reservation_status"], "resource_occupied")
        self.assertEqual(self.agent.reservation.reserved_mission_id, "mission-a")

    async def test_accept_with_wrong_missing_or_unexpected_performative_is_ignored(self):
        for performative in (PERFORMATIVE_REJECT_PROPOSAL, None, PERFORMATIVE_PROPOSE):
            with self.subTest(performative=performative):
                agent = self.make_agent()
                cfp = self.cfp("accept-cfp")
                proposal = await self.propose(cfp, agent=agent)
                before = dict(agent._proposal_context)

                replies = await self.dispatch(
                    build_accept_message(cfp, proposal, 21.0), agent=agent,
                    performative=performative,
                )

                self.assertEqual(replies, [])
                self.assertEqual(agent._proposal_context, before)
                self.assertTrue(agent.resource.available)
                self.assertIsNone(agent.reservation.reserved_mission_id)

    async def test_reject_with_wrong_missing_or_unexpected_performative_is_ignored(self):
        for performative in (PERFORMATIVE_ACCEPT_PROPOSAL, None, PERFORMATIVE_PROPOSE):
            with self.subTest(performative=performative):
                agent = self.make_agent()
                cfp = self.cfp("reject-cfp")
                proposal = await self.propose(cfp, agent=agent)
                before = dict(agent._proposal_context)

                replies = await self.dispatch(
                    build_proposal_rejection_message(cfp, proposal, 21.0), agent=agent,
                    performative=performative,
                )

                self.assertEqual(replies, [])
                self.assertEqual(agent._proposal_context, before)
                await self.assert_reserved(cfp, proposal, agent=agent)

    async def test_invalid_decision_performative_does_not_trigger_proposal_expiry(self):
        for reject in (False, True):
            with self.subTest(reject=reject):
                agent = self.make_agent()
                cfp = self.cfp("expired-cfp")
                proposal = await self.propose(cfp, agent=agent)
                before = dict(agent._proposal_context)
                # Deixar a expiração para o próximo comportamento recebido.
                agent.simulated_time = 36.0
                build = build_proposal_rejection_message if reject else build_accept_message
                wrong = PERFORMATIVE_ACCEPT_PROPOSAL if reject else PERFORMATIVE_REJECT_PROPOSAL

                replies = await self.dispatch(
                    build(cfp, proposal, 21.0), agent=agent, performative=wrong,
                )

                self.assertEqual(replies, [])
                self.assertEqual(agent._proposal_context, before)
                self.assertTrue(agent.resource.available)

    async def test_duplicate_valid_accept_remains_idempotent(self):
        cfp = self.cfp("accepted-cfp", round_number=1)
        proposal = await self.propose(cfp)
        accept = build_accept_message(cfp, proposal, 21.0)

        first = await self.dispatch(accept)
        repeated = await self.dispatch(accept)
        self.agent.set_simulated_time(36.0)
        after_expiry = await self.dispatch(accept)

        self.assertEqual(first[0].payload["reservation_status"], "reserved")
        self.assertEqual(repeated[0].payload["reservation_status"], "already_reserved")
        self.assertEqual(after_expiry[0].payload["reservation_status"], "already_reserved")
        self.assertEqual(self.agent.reservation.reserved_mission_id, "mission-1")

    async def test_duplicate_valid_reject_remains_idempotent(self):
        cfp = self.cfp("rejected-cfp", round_number=1)
        proposal = await self.propose(cfp)
        reject = build_proposal_rejection_message(cfp, proposal, 21.0)

        self.assertEqual(await self.dispatch(reject), [])
        self.assertEqual(await self.dispatch(reject), [])
        self.assertNotIn(proposal.message_id, self.agent._proposal_context)
        self.assertTrue(self.agent.resource.available)
        self.assertIsNone(self.agent.reservation.reserved_mission_id)
        self.assertEqual(await self.dispatch(cfp), [])
        late = await self.dispatch(build_accept_message(cfp, proposal, 21.0))
        self.assertEqual(late[0].payload["status"], "reservation_failed")

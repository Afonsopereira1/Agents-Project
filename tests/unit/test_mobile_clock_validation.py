import unittest
from unittest.mock import AsyncMock

from isia.communication.transport import (
    CONTRACT_NET_PROTOCOL,
    PERFORMATIVE_ACCEPT_PROPOSAL,
    PERFORMATIVE_CFP,
    build_spade_message,
    parse_spade_message,
)
from isia.domain.models import Mission, Position, ResourceState
from isia.reasoning.allocation import build_accept_message, build_cfp_message

try:
    from isia.agents.mobile import MobileResourceAgent
except ImportError:
    MobileResourceAgent = None


INVALID_TIMES = (float("nan"), float("inf"), -float("inf"), -1.0,
                 True, "21", None, 10**400)


@unittest.skipUnless(MobileResourceAgent is not None, "SPADE não está instalado")
class TestMobileClockValidation(unittest.IsolatedAsyncioTestCase):
    def agent(self, simulated_time=21.0):
        return MobileResourceAgent(
            "drone@localhost", "local-test",
            ResourceState("drone-1", "drone", Position(1, 2), True, 80.0),
            ("mobile_verification",), minimum_autonomy_percent=20.0,
            eta_seconds=4.0, energy_cost_percent=10.0, load=0.25,
            simulated_time=simulated_time,
        )

    async def dispatch(self, agent, body, *, cfp=False):
        behaviour = (
            MobileResourceAgent.ContractNetBehaviour()
            if cfp else MobileResourceAgent.AcceptBehaviour()
        )
        behaviour.set_agent(agent)
        incoming = build_spade_message(
            str(agent.jid), body,
            performative=PERFORMATIVE_CFP if cfp else PERFORMATIVE_ACCEPT_PROPOSAL,
            conversation_id=body.conversation_id,
            in_reply_to=None if cfp else body.payload["proposal_message_id"],
            protocol=CONTRACT_NET_PROTOCOL,
        )
        incoming.sender = "initiator@localhost"
        behaviour.receive = AsyncMock(return_value=incoming)
        behaviour.send = AsyncMock()
        await behaviour.run()
        return [
            parse_spade_message(call.args[0], expected_protocol=CONTRACT_NET_PROTOCOL)
            for call in behaviour.send.await_args_list
        ]

    async def proposal(self, agent):
        mission = Mission(
            "mission-1", "incident-1", "verify_incident", Position(6, 9),
            "mobile_verification", 2,
        )
        cfp = build_cfp_message(mission, 20.0, 25.0, round_number=1)
        proposal, = await self.dispatch(agent, cfp, cfp=True)
        return cfp, proposal

    def state(self, agent):
        return (
            agent.resource, agent.reservation.resource_state,
            agent.reservation.reserved_mission_id,
            dict(agent._proposal_context), set(agent._closed_cfp_ids),
            dict(agent._latest_cfp_times), dict(agent._latest_cfp_rounds),
            set(agent._accepted_proposal_ids),
        )

    async def test_constructor_rejects_invalid_times(self):
        for value in INVALID_TIMES:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.agent(value)

    async def test_invalid_setter_preserves_time_contexts_and_reservation(self):
        agent = self.agent()
        await self.proposal(agent)
        original = self.state(agent)
        for value in INVALID_TIMES:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    agent.set_simulated_time(value)
                self.assertEqual(agent.simulated_time, 21.0)
                self.assertEqual(self.state(agent), original)

    async def test_failed_clock_update_does_not_prevent_valid_idempotent_accept(self):
        agent = self.agent()
        cfp, proposal = await self.proposal(agent)
        with self.assertRaises(ValueError):
            agent.set_simulated_time(float("nan"))
        accept = build_accept_message(cfp, proposal, 21.0)
        first, = await self.dispatch(agent, accept)
        agent.set_simulated_time(36.0)
        repeated, = await self.dispatch(agent, accept)
        self.assertEqual(first.payload["reservation_status"], "reserved")
        self.assertEqual(repeated.payload["reservation_status"], "already_reserved")
        self.assertEqual(agent.reservation.reserved_mission_id, "mission-1")

    async def test_invalid_direct_clock_cannot_mutate_state_during_accept(self):
        for value in INVALID_TIMES:
            with self.subTest(value=value):
                agent = self.agent()
                cfp, proposal = await self.proposal(agent)
                original = self.state(agent)
                agent.simulated_time = value
                replies = await self.dispatch(
                    agent, build_accept_message(cfp, proposal, 999.0),
                )
                self.assertEqual(replies, [])
                self.assertEqual(self.state(agent), original)

    async def test_valid_instants_retain_their_previous_semantics(self):
        agent = self.agent(0)
        self.assertEqual(agent.simulated_time, 0)
        for value in (0, 0.5, 21.0, 21.0):
            agent.set_simulated_time(value)
            self.assertEqual(agent.simulated_time, value)

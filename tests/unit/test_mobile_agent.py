import unittest

from isia.communication.messages import Message, MessageType
from isia.communication.transport import (
    CONTRACT_NET_PROTOCOL,
    PERFORMATIVE_CFP,
    build_spade_message,
    parse_spade_message,
)
from isia.domain.models import Position, ResourceState, ResourceStatus

try:
    from spade.message import Message as SpadeMessage

    from isia.agents.mobile import MobileResourceAgent
except ImportError:
    SpadeMessage = None
    MobileResourceAgent = None


@unittest.skipUnless(SpadeMessage is not None, "SPADE não está instalado")
class TestMobileResourceBehaviour(unittest.IsolatedAsyncioTestCase):
    def _agent(self, **overrides):
        values = {
            "resource": ResourceState(
                "drone-1", "drone", Position(1, 2), True, 80.0
            ),
            "capabilities": ("mobile_verification",),
            "minimum_autonomy_percent": 20.0,
            "eta_seconds": 4.0,
            "energy_cost_percent": 10.0,
            "load": 0.25,
            "simulated_time": 21.0,
        }
        values.update(overrides)
        return MobileResourceAgent("drone@localhost", "password", **values)

    def _cfp(self, *, deadline=35.0, message_type=MessageType.CFP):
        payload = {
            "task": "verify_incident",
            "target": {"x": 6, "y": 9},
            "required_capability": "mobile_verification",
            "priority": 2,
            "deadline": deadline,
        }
        return Message(
            "cfp-1",
            message_type,
            20.0,
            payload if message_type is MessageType.CFP else {},
            incident_id="incident-1" if message_type is MessageType.CFP else None,
            mission_id="mission-1" if message_type is MessageType.CFP else None,
            conversation_id="conversation-1",
        )

    async def _run(self, agent, cfp):
        behaviour = MobileResourceAgent.ContractNetBehaviour()
        behaviour.set_agent(agent)
        incoming = build_spade_message(
            "drone@localhost",
            cfp,
            performative=PERFORMATIVE_CFP,
            conversation_id=cfp.conversation_id,
            protocol=CONTRACT_NET_PROTOCOL,
        )
        incoming.sender = "initiator@localhost"
        sent = []

        async def receive(timeout):
            return incoming

        async def send(message):
            sent.append(message)

        behaviour.receive = receive
        behaviour.send = send
        await behaviour.run()
        return sent

    async def test_behaviour_sends_correlated_proposal(self):
        sent = await self._run(self._agent(), self._cfp())

        self.assertEqual(len(sent), 1)
        response = parse_spade_message(
            sent[0], expected_protocol=CONTRACT_NET_PROTOCOL
        )
        self.assertIs(response.message_type, MessageType.PROPOSAL)
        self.assertEqual(response.payload["cfp_message_id"], "cfp-1")
        self.assertEqual(response.mission_id, "mission-1")
        self.assertEqual(response.incident_id, "incident-1")
        self.assertEqual(response.conversation_id, "conversation-1")
        self.assertEqual(sent[0].get_metadata("in-reply-to"), "cfp-1")

    async def test_proposal_context_is_available_during_send(self):
        agent = self._agent()
        cfp = self._cfp()
        behaviour = MobileResourceAgent.ContractNetBehaviour()
        behaviour.set_agent(agent)
        incoming = build_spade_message(
            "drone@localhost",
            cfp,
            performative=PERFORMATIVE_CFP,
            conversation_id=cfp.conversation_id,
            protocol=CONTRACT_NET_PROTOCOL,
        )
        incoming.sender = "initiator@localhost"
        observed = {}

        async def receive(timeout):
            return incoming

        async def send(message):
            response = parse_spade_message(
                message, expected_protocol=CONTRACT_NET_PROTOCOL
            )
            observed["context"] = agent._proposal_context.get(response.message_id)

        behaviour.receive = receive
        behaviour.send = send
        await behaviour.run()

        self.assertIsNotNone(observed["context"])
        self.assertEqual(observed["context"][0].message_id, cfp.message_id)
        self.assertEqual(observed["context"][1].message_type, MessageType.PROPOSAL)
        self.assertEqual(observed["context"][2], "initiator@localhost")

    async def test_behaviour_sends_reject_for_expired_cfp(self):
        sent = await self._run(self._agent(), self._cfp(deadline=20.0))

        response = parse_spade_message(
            sent[0], expected_protocol=CONTRACT_NET_PROTOCOL
        )
        self.assertIs(response.message_type, MessageType.REJECT)
        self.assertEqual(response.payload["reason"], "cfp_expired")

    async def test_behaviour_sends_reject_for_local_ineligibility(self):
        cases = (
            (
                {
                    "resource": ResourceState(
                        "drone-1",
                        "drone",
                        Position(1, 2),
                        False,
                        80.0,
                        ResourceStatus.UNAVAILABLE,
                    )
                },
                "resource_unavailable",
            ),
            ({"capabilities": ("thermal_scan",)}, "capability_mismatch"),
            (
                {
                    "resource": ResourceState(
                        "drone-1", "drone", Position(1, 2), True, 25.0
                    )
                },
                "autonomy_insufficient",
            ),
        )
        for overrides, reason in cases:
            with self.subTest(reason=reason):
                sent = await self._run(self._agent(**overrides), self._cfp())
                response = parse_spade_message(
                    sent[0], expected_protocol=CONTRACT_NET_PROTOCOL
                )
                self.assertIs(response.message_type, MessageType.REJECT)
                self.assertEqual(response.payload["reason"], reason)

    async def test_behaviour_ignores_non_cfp_message(self):
        sent = await self._run(
            self._agent(),
            Message(
                "alert-1",
                MessageType.ALERT,
                20.0,
                {},
                conversation_id="conversation-1",
            ),
        )

        self.assertEqual(sent, [])


if __name__ == "__main__":
    unittest.main()

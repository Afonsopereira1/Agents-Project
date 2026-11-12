import unittest

from isia.communication.messages import Message, MessageType
from isia.domain.models import Position, ResourceState

try:
    from spade.message import Message as SpadeMessage

    from contract_net_demo import (
        ContractNetInitiatorAgent,
        confirmation_matches_accept,
        response_matches_cfp,
    )
    from isia.communication.transport import (
        CONTRACT_NET_PROTOCOL,
        ONTOLOGY,
        PERFORMATIVE_INFORM,
        PERFORMATIVE_PROPOSE,
        build_spade_message,
        parse_spade_message,
    )
    from isia.reasoning.allocation import (
        LocalResourceReservation,
        build_accept_message,
        build_reservation_status_message,
    )
except ImportError:
    SpadeMessage = None
    ContractNetInitiatorAgent = None


@unittest.skipUnless(SpadeMessage is not None, "SPADE não está instalado")
class TestContractNetDemoCorrelation(unittest.TestCase):
    def setUp(self):
        self.cfp = Message(
            "cfp-1",
            MessageType.CFP,
            20.0,
            {
                "task": "verify_incident",
                "target": {"x": 6, "y": 9},
                "required_capability": "mobile_verification",
                "priority": 2,
                "deadline": 35.0,
            },
            incident_id="incident-1",
            mission_id="mission-1",
            conversation_id="conversation-1",
        )

    def incoming(self, response, sender="drone@localhost", performative="propose"):
        incoming = SpadeMessage(
            to="initiator@localhost",
            sender=sender,
            body=response.to_json(),
        )
        for key, value in {
            "ontology": ONTOLOGY,
            "protocol": CONTRACT_NET_PROTOCOL,
            "performative": performative,
            "conversation-id": self.cfp.conversation_id,
            "in-reply-to": self.cfp.message_id,
        }.items():
            incoming.set_metadata(key, value)
        return incoming

    def response(self, message_type=MessageType.PROPOSAL, **overrides):
        payload = {
            "cfp_message_id": self.cfp.message_id,
            "bid": {
                "mission_id": self.cfp.mission_id,
                "resource_id": "drone-demo",
                "eta": 4.0,
                "energy_cost": 10.0,
                "load": 0.25,
            },
        }
        if message_type is MessageType.REJECT:
            payload = {"cfp_message_id": self.cfp.message_id, "reason": "cfp_expired"}
        values = {
            "message_id": "response-1",
            "message_type": message_type,
            "created_at": 21.0,
            "payload": payload,
            "incident_id": self.cfp.incident_id,
            "mission_id": self.cfp.mission_id,
            "source_id": "drone-demo",
            "conversation_id": self.cfp.conversation_id,
        }
        values.update(overrides)
        return Message(**values)

    def test_valid_response_is_correlated(self):
        response = self.response()
        self.assertTrue(
            response_matches_cfp(
                self.incoming(response),
                response,
                self.cfp,
                {"drone@localhost": "drone-demo"},
            )
        )

    def test_invalid_sender_or_conversation_is_rejected(self):
        response = self.response()
        self.assertFalse(
            response_matches_cfp(
                self.incoming(response, sender="unknown@localhost"),
                response,
                self.cfp,
                {"drone@localhost": "drone-demo"},
            )
        )
        response = self.response(conversation_id="other-conversation")
        self.assertFalse(
            response_matches_cfp(
                self.incoming(response),
                response,
                self.cfp,
                {"drone@localhost": "drone-demo"},
            )
        )

    def test_reject_response_and_explicit_timeout_are_supported(self):
        response = self.response(
            message_type=MessageType.REJECT,
            message_id="reject-1",
        )
        incoming = self.incoming(response, performative="reject-proposal")
        self.assertTrue(
            response_matches_cfp(
                incoming,
                response,
                self.cfp,
                {"drone@localhost": "drone-demo"},
            )
        )
        self.assertEqual(response.payload["reason"], "cfp_expired")

    def test_confirmation_is_correlated_with_accept_and_resource(self):
        proposal = self.response()
        accept = build_accept_message(self.cfp, proposal, 22.0)
        result = LocalResourceReservation(
            ResourceState("drone-demo", "drone", Position(1, 2), True, 80.0)
        ).reserve("mission-1")
        status = build_reservation_status_message(
            accept, result, resource_id="drone-demo", created_at=22.0
        )
        incoming = SpadeMessage(
            to="initiator@localhost", sender="drone@localhost", body=status.to_json()
        )
        for key, value in {
            "ontology": ONTOLOGY,
            "protocol": CONTRACT_NET_PROTOCOL,
            "performative": PERFORMATIVE_INFORM,
            "conversation-id": self.cfp.conversation_id,
            "in-reply-to": accept.message_id,
        }.items():
            incoming.set_metadata(key, value)

        self.assertTrue(
            confirmation_matches_accept(
                incoming,
                status,
                accept,
                winner_jid="drone@localhost",
                resource_id="drone-demo",
                initiator_jid="initiator@localhost",
            )
        )
        incoming.sender = "other@localhost"
        self.assertFalse(
            confirmation_matches_accept(
                incoming,
                status,
                accept,
                winner_jid="drone@localhost",
                resource_id="drone-demo",
                initiator_jid="initiator@localhost",
            )
        )


@unittest.skipUnless(SpadeMessage is not None, "SPADE não está instalado")
class TestContractNetInitiatorTimeout(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_real_termina_sem_fabricar_respostas(self):
        from isia.domain.models import Mission

        agent = ContractNetInitiatorAgent(
            "initiator@localhost",
            "password",
            Mission(
                "mission-1",
                "incident-1",
                "verify_incident",
                Position(6, 9),
                "mobile_verification",
                2,
            ),
            {"drone@localhost": "drone-demo"},
            simulated_time=20.0,
            deadline=35.0,
            receive_timeout=0.01,
        )
        behaviour = ContractNetInitiatorAgent.ContractNetBehaviour()
        behaviour.set_agent(agent)
        sent = []

        async def receive(timeout):
            return None

        async def send(message):
            sent.append(message)

        behaviour.receive = receive
        behaviour.send = send
        await behaviour.run()

        self.assertEqual(len(sent), 1)
        self.assertEqual(agent.responses, {})

    async def test_confirmation_timeout_does_not_retry_accept_or_reserve_mission(self):
        from isia.domain.models import Mission

        agent = ContractNetInitiatorAgent(
            "initiator@localhost",
            "password",
            Mission(
                "mission-1",
                "incident-1",
                "verify_incident",
                Position(6, 9),
                "mobile_verification",
                2,
            ),
            {"drone@localhost": "drone-demo"},
            simulated_time=20.0,
            deadline=35.0,
            receive_timeout=1.0,
            max_rounds=2,
        )
        behaviour = ContractNetInitiatorAgent.ContractNetBehaviour()
        behaviour.set_agent(agent)
        sent = []
        proposal_sent = False

        async def receive(timeout):
            nonlocal proposal_sent
            if proposal_sent:
                return None
            cfp = parse_spade_message(
                sent[0], expected_protocol=CONTRACT_NET_PROTOCOL
            )
            proposal = Message(
                "proposal-drone",
                MessageType.PROPOSAL,
                21.0,
                {
                    "cfp_message_id": cfp.message_id,
                    "bid": {
                        "mission_id": cfp.mission_id,
                        "resource_id": "drone-demo",
                        "eta": 4.0,
                        "energy_cost": 10.0,
                        "load": 0.25,
                    },
                },
                incident_id=cfp.incident_id,
                mission_id=cfp.mission_id,
                source_id="drone-demo",
                conversation_id=cfp.conversation_id,
            )
            incoming = build_spade_message(
                "initiator@localhost",
                proposal,
                performative=PERFORMATIVE_PROPOSE,
                conversation_id=cfp.conversation_id,
                in_reply_to=cfp.message_id,
                protocol=CONTRACT_NET_PROTOCOL,
            )
            incoming.sender = "drone@localhost"
            proposal_sent = True
            return incoming

        async def send(message):
            sent.append(message)

        behaviour.receive = receive
        behaviour.send = send
        await behaviour.run()

        message_types = [
            parse_spade_message(item, expected_protocol=CONTRACT_NET_PROTOCOL).message_type
            for item in sent
        ]
        self.assertEqual(message_types.count(MessageType.ACCEPT), 1)
        self.assertEqual(message_types.count(MessageType.CFP), 1)
        self.assertEqual(agent.result.outcome, "confirmation_unknown")
        self.assertEqual(agent.mission.status.value, "proposed")

    async def test_two_rounds_recover_from_explicit_reservation_rejection(self):
        from isia.domain.models import Mission, ResourceStatus

        agent = ContractNetInitiatorAgent(
            "initiator@localhost",
            "password",
            Mission(
                "mission-1",
                "incident-1",
                "verify_incident",
                Position(6, 9),
                "mobile_verification",
                2,
            ),
            {
                "drone@localhost": "drone-demo",
                "vehicle@localhost": "vehicle-demo",
            },
            simulated_time=20.0,
            deadline=35.0,
            receive_timeout=1.0,
            max_rounds=2,
        )
        behaviour = ContractNetInitiatorAgent.ContractNetBehaviour()
        behaviour.set_agent(agent)
        sent = []
        receive_call = 0

        def sent_body(message_type):
            for outgoing in sent:
                body = parse_spade_message(
                    outgoing, expected_protocol=CONTRACT_NET_PROTOCOL
                )
                if body.message_type is message_type:
                    yield outgoing, body

        def incoming_for(body, sender, performative):
            incoming = build_spade_message(
                "initiator@localhost",
                body,
                performative=performative,
                conversation_id=body.conversation_id,
                in_reply_to=(
                    body.payload.get("cfp_message_id")
                    if body.message_type is MessageType.PROPOSAL
                    else body.payload["accept_message_id"]
                ),
                protocol=CONTRACT_NET_PROTOCOL,
            )
            incoming.sender = sender
            return incoming

        def proposal(cfp, message_id, resource_id):
            return Message(
                message_id,
                MessageType.PROPOSAL,
                21.0,
                {
                    "cfp_message_id": cfp.message_id,
                    "bid": {
                        "mission_id": cfp.mission_id,
                        "resource_id": resource_id,
                        "eta": 4.0,
                        "energy_cost": 10.0,
                        "load": 0.25,
                    },
                },
                incident_id=cfp.incident_id,
                mission_id=cfp.mission_id,
                source_id=resource_id,
                conversation_id=cfp.conversation_id,
            )

        async def receive(timeout):
            nonlocal receive_call
            receive_call += 1
            if receive_call == 1:
                first_cfp = next(sent_body(MessageType.CFP))[1]
                return incoming_for(
                    proposal(first_cfp, "proposal-drone", "drone-demo"),
                    "drone@localhost",
                    PERFORMATIVE_PROPOSE,
                )
            if receive_call == 2:
                return None
            if receive_call == 3:
                first_accept = list(sent_body(MessageType.ACCEPT))[0][1]
                failed_result = LocalResourceReservation(
                    ResourceState(
                        "drone-demo",
                        "drone",
                        Position(1, 2),
                        False,
                        80.0,
                        ResourceStatus.UNAVAILABLE,
                    )
                ).reserve("mission-1")
                status = build_reservation_status_message(
                    first_accept,
                    failed_result,
                    resource_id="drone-demo",
                    created_at=22.0,
                )
                return incoming_for(status, "drone@localhost", PERFORMATIVE_INFORM)
            if receive_call == 4:
                cfps = list(sent_body(MessageType.CFP))
                second_cfp = cfps[-1][1]
                return incoming_for(
                    proposal(second_cfp, "proposal-vehicle", "vehicle-demo"),
                    "vehicle@localhost",
                    PERFORMATIVE_PROPOSE,
                )
            if receive_call == 5:
                return None
            second_accept = list(sent_body(MessageType.ACCEPT))[-1][1]
            confirmed_result = LocalResourceReservation(
                ResourceState(
                    "vehicle-demo", "vehicle", Position(1, 2), True, 80.0
                )
            ).reserve("mission-1")
            status = build_reservation_status_message(
                second_accept,
                confirmed_result,
                resource_id="vehicle-demo",
                created_at=24.0,
            )
            return incoming_for(status, "vehicle@localhost", PERFORMATIVE_INFORM)

        async def send(message):
            sent.append(message)

        behaviour.receive = receive
        behaviour.send = send
        await behaviour.run()

        cfps = [body for _, body in sent_body(MessageType.CFP)]
        accepts = [body for _, body in sent_body(MessageType.ACCEPT)]
        self.assertEqual(len(cfps), 4)  # dois recursos, duas rondas
        self.assertEqual(len(accepts), 2)
        self.assertEqual(len(agent.round_history), 2)
        self.assertEqual(
            [cfp.payload["round_number"] for cfp in agent.round_history], [1, 2],
        )
        self.assertNotEqual(cfps[0].message_id, cfps[2].message_id)
        self.assertNotEqual(cfps[0].conversation_id, cfps[2].conversation_id)
        self.assertEqual(agent.mission.status.value, "reserved")
        self.assertEqual(agent.result.outcome, "reservation_confirmed")
        self.assertEqual(agent.result.rounds, 2)


if __name__ == "__main__":
    unittest.main()

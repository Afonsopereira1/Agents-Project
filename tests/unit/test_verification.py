import unittest

from isia.domain.models import Observation, Position


try:
    from spade.message import Message as SpadeMessage

    from isia.agents.informant import InformantAgent
    from isia.agents.sensor import SensorAgent
    from isia.communication.messages import Message, MessageType
    from isia.communication.transport import parse_spade_message
except ImportError:
    SpadeMessage = None


class LocalFeed:
    def __init__(self, observations):
        self.observations = tuple(observations)

    def recent(self):
        return self.observations


def observation(event_id, source_id, position=(5, 6), observed_at=1.0):
    return Observation(
        event_id, source_id, "gunshot_like_sound", Position(*position), observed_at, 0.8
    )


@unittest.skipUnless(SpadeMessage is not None, "SPADE não está instalado")
class TestRealObservationVerification(unittest.IsolatedAsyncioTestCase):
    async def test_sensor_request_transporta_observacao_do_feed_local(self):
        from unittest.mock import AsyncMock, Mock

        local = observation("obs-001", "sensor_01")
        agent = Mock(
            observation_feed=LocalFeed((local,)),
            created_at=1.0,
            informant_jid="informant@localhost",
            conversation_id=None,
            response=None,
        )
        agent.loop = __import__("asyncio").get_running_loop()
        behaviour = SensorAgent.VerificationBehaviour()
        behaviour.set_agent(agent)
        behaviour.send = AsyncMock()
        behaviour.receive = AsyncMock(return_value=None)

        await behaviour.run()

        outgoing = behaviour.send.await_args.args[0]
        request = parse_spade_message(outgoing)
        self.assertEqual(request.created_at, 1.0)
        self.assertEqual(request.payload["observation"]["event_id"], "obs-001")
        self.assertEqual(request.payload["observation"]["source_id"], "sensor_01")

    async def test_informant_responde_com_observacoes_do_seu_feed(self):
        from unittest.mock import AsyncMock, Mock

        local = observation("obs-002", "sensor_02", position=(6, 6))
        request = Message(
            "request-001",
            MessageType.VERIFY_REQUEST,
            1.0,
            {"observation": {"event_id": "obs-001"}},
            incident_id="incident-obs-001",
            conversation_id="conversation-001",
        )
        incoming = SpadeMessage(
            to="informant@localhost",
            sender="sensor@localhost",
            body=request.to_json(),
        )
        for key, value in {
            "performative": "request",
            "ontology": "isia",
            "protocol": "verification",
            "conversation-id": "conversation-001",
        }.items():
            incoming.set_metadata(key, value)

        agent = Mock(
            observation_feed=LocalFeed((local,)),
            source_id="sensor_02",
            created_at=1.0,
            loop=__import__("asyncio").get_running_loop(),
        )
        behaviour = InformantAgent.VerificationBehaviour()
        behaviour.set_agent(agent)
        behaviour.receive = AsyncMock(return_value=incoming)
        behaviour.send = AsyncMock()

        await behaviour.run()

        response = parse_spade_message(behaviour.send.await_args.args[0])
        self.assertEqual(response.payload["request_message_id"], "request-001")
        self.assertEqual(response.payload["status"], "observations_available")
        self.assertEqual(response.payload["observations"][0]["event_id"], "obs-002")
        self.assertNotIn("supports_event", response.payload)

    async def test_informant_indica_ausencia_sem_inventar_evidencia(self):
        from unittest.mock import AsyncMock, Mock

        request = Message(
            "request-002",
            MessageType.VERIFY_REQUEST,
            1.0,
            {"observation": {"event_id": "obs-001"}},
            incident_id="incident-obs-001",
            conversation_id="conversation-002",
        )
        incoming = SpadeMessage(
            to="informant@localhost",
            sender="sensor@localhost",
            body=request.to_json(),
        )
        for key, value in {
            "performative": "request",
            "ontology": "isia",
            "protocol": "verification",
            "conversation-id": "conversation-002",
        }.items():
            incoming.set_metadata(key, value)

        agent = Mock(
            observation_feed=LocalFeed(()),
            source_id="sensor_02",
            created_at=1.0,
            loop=__import__("asyncio").get_running_loop(),
        )
        behaviour = InformantAgent.VerificationBehaviour()
        behaviour.set_agent(agent)
        behaviour.receive = AsyncMock(return_value=incoming)
        behaviour.send = AsyncMock()

        await behaviour.run()

        response = parse_spade_message(behaviour.send.await_args.args[0])
        self.assertEqual(response.payload["status"], "no_data")
        self.assertEqual(response.payload["observations"], [])

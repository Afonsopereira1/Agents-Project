import asyncio
import logging
import time
import unittest
from unittest.mock import AsyncMock, Mock, patch

from isia.communication.messages import Message, MessageType, model_to_dict
from isia.communication.transport import parse_spade_message
from isia.agents.sensor import SensorAgent
from isia.domain.models import Observation, Position


class LocalFeed:
    def __init__(self, observations):
        self.observations = tuple(observations)

    def recent(self):
        return self.observations


class TestSensorTimeout(unittest.IsolatedAsyncioTestCase):
    async def test_termina_sem_resposta_e_regista_timeout(self):
        agent_mock = Mock(
            conversation_id=None,
            response=None,
            informant_jid="informant@localhost",
        )
        agent_mock.loop = asyncio.get_running_loop()

        behaviour = SensorAgent.VerificationBehaviour()
        behaviour.set_agent(agent_mock)
        behaviour.send = AsyncMock()

        async def receive_without_response(timeout):
            await asyncio.sleep(timeout)
            return None

        behaviour.receive = receive_without_response

        with patch(
            "isia.agents.sensor.RESPONSE_TIMEOUT_SECONDS", 0.01
        ), self.assertLogs(
            "isia.agents.sensor", level=logging.WARNING
        ) as captured:
            started = time.monotonic()
            await behaviour.run()
            elapsed = time.monotonic() - started

        self.assertLess(elapsed, 1.0)
        self.assertIsNone(agent_mock.response)
        behaviour.send.assert_awaited_once()
        self.assertTrue(
            any("Timeout à espera de VERIFY_RESPONSE" in line for line in captured.output)
        )

    async def test_nova_verificacao_preserva_historico_anterior(self):
        agent_mock = Mock(
            conversation_id=None,
            response=None,
            informant_jid="informant@localhost",
        )
        agent_mock.loop = asyncio.get_running_loop()
        behaviour = SensorAgent.VerificationBehaviour()
        behaviour.set_agent(agent_mock)
        behaviour.send = AsyncMock()
        behaviour.receive = AsyncMock(return_value=None)

        with patch("isia.agents.sensor.RESPONSE_TIMEOUT_SECONDS", 0.01):
            await behaviour.run()
            first_history = {
                conversation_id: dict(requests)
                for conversation_id, requests in agent_mock.verification_history.items()
            }
            await behaviour.run()

        self.assertEqual(len(first_history), 1)
        self.assertEqual(len(agent_mock.verification_history), 2)
        for requests in agent_mock.verification_history.values():
            self.assertEqual(len(requests), 1)
            record = next(iter(requests.values()))
            self.assertEqual(record["classification"], "timeout")
            self.assertEqual(record["decision"], "observe")
            self.assertEqual(record["evidence_observation_ids"], ())

    async def test_resposta_compativel_que_chega_depois_do_timeout_nao_confirma(self):
        initial = Observation(
            "obs-timeout-initial", "sensor_01", "gunshot_like_sound", Position(5, 6), 1.0, 0.8
        )
        corroborating = Observation(
            "obs-timeout-late", "sensor_02", "gunshot_like_sound", Position(5, 6), 1.0, 0.8
        )
        agent_mock = Mock(
            observation_feed=LocalFeed((initial,)),
            created_at=1.0,
            response=None,
            informant_jid="informant@localhost",
            eligible_source_ids=("sensor_02",),
            max_distance=1.0,
            max_time_difference=1.0,
            minimum_compatible_sources=1,
        )
        agent_mock.loop = asyncio.get_running_loop()
        behaviour = SensorAgent.VerificationBehaviour()
        behaviour.set_agent(agent_mock)
        sent = []
        late_messages = []

        async def send(message):
            sent.append(message)

        async def receive(timeout):
            await asyncio.sleep(timeout)
            request = parse_spade_message(sent[0])
            late = Message(
                "response-late",
                MessageType.VERIFY_RESPONSE,
                1.0,
                {
                    "request_message_id": request.message_id,
                    "status": "observations_available",
                    "observations": [model_to_dict(corroborating)],
                },
                conversation_id=request.conversation_id,
            )
            late_messages.append(late)
            return None

        behaviour.send = AsyncMock(side_effect=send)
        behaviour.receive = receive

        with patch("isia.agents.sensor.RESPONSE_TIMEOUT_SECONDS", 0.01):
            await behaviour.run()

        self.assertEqual(agent_mock.decision["decision"], "observe")
        self.assertEqual(agent_mock.decision["reason"], "timeout")
        self.assertEqual(agent_mock.decision["compatible_observation_ids"], ())
        self.assertIsNone(agent_mock.response)
        self.assertEqual(len(late_messages), 1)

    async def test_mensagem_tardia_de_conversa_anterior_nao_altera_resultado(self):
        initial = Observation(
            "obs-previous-conversation", "sensor_01", "gunshot_like_sound", Position(5, 6), 1.0, 0.8
        )
        agent_mock = Mock(
            observation_feed=LocalFeed((initial,)),
            created_at=1.0,
            response=None,
            informant_jid="informant@localhost",
            eligible_source_ids=("sensor_02",),
            max_distance=1.0,
            max_time_difference=1.0,
            minimum_compatible_sources=1,
        )
        agent_mock.loop = asyncio.get_running_loop()
        behaviour = SensorAgent.VerificationBehaviour()
        behaviour.set_agent(agent_mock)
        late_messages = []

        async def receive(timeout):
            await asyncio.sleep(timeout)
            return None

        behaviour.send = AsyncMock()
        behaviour.receive = receive

        with patch("isia.agents.sensor.RESPONSE_TIMEOUT_SECONDS", 0.01):
            await behaviour.run()

        decision_after_timeout = dict(agent_mock.decision)
        late_messages.append(
            Message(
                "response-previous-conversation",
                MessageType.VERIFY_RESPONSE,
                1.0,
                {
                    "request_message_id": "request-previous-conversation",
                    "status": "observations_available",
                    "observations": [],
                },
                conversation_id="conversation-previous",
            )
        )
        self.assertEqual(decision_after_timeout["decision"], "observe")
        self.assertEqual(decision_after_timeout["reason"], "timeout")
        self.assertEqual(decision_after_timeout["compatible_observation_ids"], ())
        self.assertEqual(len(late_messages), 1)
        self.assertEqual(agent_mock.decision, decision_after_timeout)
        records = [
            record
            for requests in agent_mock.verification_history.values()
            for record in requests.values()
        ]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["classification"], "timeout")
        self.assertEqual(records[0]["evidence_observation_ids"], ())

import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from isia.communication.messages import Message, MessageType, model_to_dict
from isia.communication.transport import build_spade_message, parse_spade_message
from isia.domain.models import Observation, Position

try:
    from isia.agents.sensor import SensorAgent
except ImportError:
    SensorAgent = None


class LocalFeed:
    def __init__(self, observation):
        self.observation = observation

    def recent(self):
        return (self.observation,)


@unittest.skipUnless(SensorAgent is not None, "SPADE não está instalado")
class TestSensorResponseDeadline(unittest.IsolatedAsyncioTestCase):
    def _behaviour(self):
        local = Observation(
            "initial", "sensor_01", "gunshot_like_sound", Position(5, 6), 1.0, 0.8
        )
        agent = Mock(
            loop=asyncio.get_running_loop(),
            observation_feed=LocalFeed(local),
            created_at=1.0,
            informant_jid="informant@localhost",
            response=None,
            eligible_source_ids=("sensor_02",),
            max_distance=2.0,
            max_time_difference=1.0,
            minimum_compatible_sources=1,
            incompatibility_rules=None,
            compatibility_rules=None,
            verification_history={},
        )
        behaviour = SensorAgent.VerificationBehaviour()
        behaviour.set_agent(agent)
        behaviour.send = AsyncMock()
        return behaviour, agent

    def _response(self, request, *, conversation_id=None, invalid_payload=False):
        corroborating = Observation(
            "corroborating", "sensor_02", "gunshot_like_sound", Position(6, 6), 1.0, 0.8
        )
        response = Message(
            "verification-response",
            MessageType.VERIFY_RESPONSE,
            1.0,
            {
                "request_message_id": request.message_id,
                "status": "observations_available",
                "observations": [] if invalid_payload else [model_to_dict(corroborating)],
            },
            incident_id=request.incident_id,
            source_id="sensor_02",
            conversation_id=conversation_id or request.conversation_id,
        )
        incoming = build_spade_message(
            "sensor@localhost", response, performative="inform",
            conversation_id=response.conversation_id, in_reply_to=request.message_id,
        )
        incoming.sender = "informant@localhost"
        return incoming

    async def test_resposta_valida_apos_rejeicao_ainda_e_avaliada(self):
        for rejection in ("malformed", "another_conversation", "invalid_payload"):
            with self.subTest(rejection=rejection):
                behaviour, agent = self._behaviour()
                calls = 0

                async def receive(timeout):
                    nonlocal calls
                    calls += 1
                    request = parse_spade_message(behaviour.send.await_args.args[0])
                    if calls == 1:
                        incoming = self._response(
                            request,
                            conversation_id="another-conversation" if rejection == "another_conversation" else None,
                            invalid_payload=rejection == "invalid_payload",
                        )
                        if rejection == "malformed":
                            incoming.body = "{invalid-json"
                        return incoming
                    return self._response(request)

                behaviour.receive = AsyncMock(side_effect=receive)
                await behaviour.run()

                self.assertEqual(agent.decision["decision"], "request_mobile_verification")
                self.assertIsNotNone(agent.response)
                self.assertEqual(behaviour.receive.await_count, 2)
                record = next(iter(agent.verification_history[agent.conversation_id].values()))
                self.assertEqual(record["decision"], "request_mobile_verification")
                expected_reason = "invalid_correlation" if rejection == "another_conversation" else "invalid_response"
                self.assertEqual(record["rejected_responses"][0]["reason"], expected_reason)

    async def test_rejeicoes_nao_renovam_prazo_global(self):
        behaviour, agent = self._behaviour()
        now = [100.0]
        receive_timeouts = []
        elapsed_per_receive = iter((3.0, 5.0, 2.0))

        async def receive(timeout):
            receive_timeouts.append(timeout)
            now[0] += next(elapsed_per_receive)
            request = parse_spade_message(behaviour.send.await_args.args[0])
            incoming = self._response(request)
            incoming.body = "{invalid-json"
            return incoming

        behaviour.receive = AsyncMock(side_effect=receive)
        with patch("isia.agents.sensor.RESPONSE_TIMEOUT_SECONDS", 10.0), patch(
            "isia.agents.sensor.monotonic", side_effect=lambda: now[0], create=True
        ):
            await behaviour.run()

        self.assertEqual(receive_timeouts, [10.0, 7.0, 2.0])
        self.assertEqual(agent.decision["decision"], "observe")
        self.assertEqual(agent.decision["reason"], "invalid_response")
        self.assertIsNone(agent.response)
        record = next(iter(agent.verification_history[agent.conversation_id].values()))
        self.assertTrue(record["response_wait_timed_out"])

    async def test_resposta_valida_recebida_apos_prazo_nao_e_aplicada(self):
        behaviour, agent = self._behaviour()
        now = [100.0]

        async def receive(timeout):
            now[0] += 11.0
            request = parse_spade_message(behaviour.send.await_args.args[0])
            return self._response(request)

        behaviour.receive = AsyncMock(side_effect=receive)
        with patch("isia.agents.sensor.RESPONSE_TIMEOUT_SECONDS", 10.0), patch(
            "isia.agents.sensor.monotonic", side_effect=lambda: now[0], create=True
        ):
            await behaviour.run()

        self.assertEqual(agent.decision["decision"], "observe")
        self.assertEqual(agent.decision["reason"], "timeout")
        self.assertIsNone(agent.response)


if __name__ == "__main__":
    unittest.main()

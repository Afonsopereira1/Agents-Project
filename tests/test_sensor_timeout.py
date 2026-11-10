import asyncio
import logging
import time
import unittest
from unittest.mock import AsyncMock, Mock, patch

from isia.agents.sensor import SensorAgent


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

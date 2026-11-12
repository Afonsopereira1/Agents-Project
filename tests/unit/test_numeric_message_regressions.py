"""Entradas numéricas extremas não devem interromper o processamento de mensagens."""

import asyncio
import json
import unittest
from dataclasses import replace
from unittest.mock import AsyncMock, Mock

from isia.communication.messages import (
    Message,
    MessageType,
    deserialize_model,
    model_to_dict,
    serialize_model,
)
from isia.domain.models import Bid, Observation, Position, ResourceState

try:
    from isia.agents.informant import InformantAgent
    from isia.agents.mobile import MobileResourceAgent
    from isia.agents.sensor import SensorAgent
    from isia.communication.transport import build_spade_message, parse_spade_message
except ImportError:
    InformantAgent = MobileResourceAgent = SensorAgent = None


HUGE_INTEGER = 10 ** 400


class TestNumericModelValidation(unittest.TestCase):
    def test_large_message_times_are_rejected_before_and_after_json(self):
        message = Message("request", MessageType.VERIFY_REQUEST, 1.0, {})
        data = message.to_dict()
        data["created_at"] = HUGE_INTEGER
        with self.assertRaises(ValueError):
            Message("request", MessageType.VERIFY_REQUEST, HUGE_INTEGER, {})
        with self.assertRaises(ValueError):
            Message.from_json(json.dumps(data))

    def test_large_cfp_deadline_is_rejected_before_and_after_json(self):
        data = {
            "schema_version": 1,
            "message_id": "cfp",
            "message_type": "CFP",
            "created_at": 1.0,
            "incident_id": "incident",
            "mission_id": "mission",
            "conversation_id": "conversation",
            "payload": {
                "task": "verify_incident",
                "target": {"x": 5, "y": 6},
                "required_capability": "mobile_verification",
                "priority": 1,
                "deadline": HUGE_INTEGER,
            },
        }
        with self.assertRaises(ValueError):
            Message.from_dict(data)
        with self.assertRaises(ValueError):
            Message.from_json(json.dumps(data))

    def test_large_model_numbers_are_rejected_before_and_after_json(self):
        observation = Observation("obs", "sensor", "sound", Position(1, 2), 1.0, 0.8)
        resource = ResourceState("drone", "drone", Position(1, 2), True, 80.0)
        bid = Bid("mission", "drone", 2.0, 10.0, 0.25)
        cases = (
            (observation, "observed_at"),
            (observation, "intensity_score"),
            (resource, "autonomy_percent"),
            (bid, "eta"),
            (bid, "energy_cost"),
            (bid, "load"),
        )
        for model, field in cases:
            with self.subTest(model=type(model).__name__, field=field):
                with self.assertRaises(ValueError):
                    replace(model, **{field: HUGE_INTEGER})
                data = model_to_dict(model)
                data[field] = HUGE_INTEGER
                with self.assertRaises(ValueError):
                    deserialize_model(json.dumps(data), type(model))

    def test_representable_large_numbers_and_arbitrary_positions_remain_valid(self):
        position = Position(HUGE_INTEGER, 0)
        self.assertEqual(deserialize_model(serialize_model(position), Position), position)
        observation = Observation("obs", "sensor", "sound", position, 1e308, 1.0, 0.0)
        bid = Bid("mission", "drone", 1e308, 1e308, 1.0)
        for model in (observation, bid):
            self.assertEqual(deserialize_model(serialize_model(model), type(model)), model)
        self.assertEqual(Message("request", MessageType.VERIFY_REQUEST, 1e308, {}).created_at, 1e308)


@unittest.skipUnless(InformantAgent is not None, "SPADE não está instalado")
class TestNumericMessageBehaviours(unittest.IsolatedAsyncioTestCase):
    async def test_informant_processes_valid_request_after_large_created_at(self):
        request = Message("request", MessageType.VERIFY_REQUEST, 1.0, {},
                          conversation_id="conversation")
        incoming = build_spade_message(
            "informant@localhost", request, performative="request",
            conversation_id=request.conversation_id,
        )
        incoming.sender = "sensor@localhost"
        invalid = build_spade_message(
            "informant@localhost", request, performative="request",
            conversation_id=request.conversation_id,
        )
        invalid.sender = incoming.sender
        data = request.to_dict()
        data["created_at"] = HUGE_INTEGER
        invalid.body = json.dumps(data)
        agent = Mock(
            loop=asyncio.get_running_loop(), observation_feed=None,
            source_id="sensor_02", created_at=1.0,
        )
        behaviour = InformantAgent.VerificationBehaviour()
        behaviour.set_agent(agent)
        behaviour.receive = AsyncMock(side_effect=[invalid, incoming])

        async def send(message):
            self.assertEqual(parse_spade_message(message).payload["status"], "no_data")
            behaviour.kill(exit_code="valid_request_processed")

        behaviour.send = AsyncMock(side_effect=send)
        await behaviour._step()
        self.assertEqual(behaviour.exit_code, "valid_request_processed")
        self.assertEqual(behaviour.receive.await_count, 2)
        self.assertEqual(behaviour.send.await_count, 1)
        agent.remove_behaviour.assert_called_once_with(behaviour)

    async def test_mobile_processes_valid_cfp_after_large_deadline(self):
        resource = ResourceState("drone", "drone", Position(1, 2), True, 80.0)
        agent = MobileResourceAgent(
            "drone@localhost", "test-password", resource, ("mobile_verification",),
            minimum_autonomy_percent=20.0, eta_seconds=4.0,
            energy_cost_percent=10.0, load=0.25, simulated_time=1.0,
        )
        cfp = Message("cfp", MessageType.CFP, 1.0, {
            "task": "verify_incident", "target": {"x": 5, "y": 6},
            "required_capability": "mobile_verification", "priority": 1,
            "deadline": 10.0,
        }, incident_id="incident", mission_id="mission", conversation_id="conversation")
        incoming = build_spade_message(
            "drone@localhost", cfp, performative="cfp",
            conversation_id=cfp.conversation_id, protocol="contract-net",
        )
        incoming.sender = "initiator@localhost"
        invalid = build_spade_message(
            "drone@localhost", cfp, performative="cfp",
            conversation_id=cfp.conversation_id, protocol="contract-net",
        )
        invalid.sender = incoming.sender
        data = cfp.to_dict()
        data["payload"] = dict(data["payload"], deadline=HUGE_INTEGER)
        invalid.body = json.dumps(data)
        behaviour = MobileResourceAgent.ContractNetBehaviour()
        agent.add_behaviour(behaviour)
        calls = 0

        async def receive(timeout):
            nonlocal calls
            calls += 1
            if calls == 1:
                return invalid
            self.assertEqual(agent.reservation.resource_state, resource)
            self.assertEqual(agent._proposal_context, {})
            self.assertEqual(agent._closed_cfp_ids, set())
            return incoming

        async def send(message):
            response = parse_spade_message(message, expected_protocol="contract-net")
            self.assertIs(response.message_type, MessageType.PROPOSAL)
            behaviour.kill(exit_code="valid_cfp_processed")

        behaviour.receive = AsyncMock(side_effect=receive)
        behaviour.send = AsyncMock(side_effect=send)
        await behaviour._step()
        self.assertEqual(behaviour.exit_code, "valid_cfp_processed")
        self.assertEqual(behaviour.receive.await_count, 2)
        self.assertEqual(behaviour.send.await_count, 1)
        self.assertEqual(agent.reservation.resource_state, resource)
        self.assertEqual(len(agent._proposal_context), 1)

    async def _sensor_after_invalid_observation(self, field, value):
        local = Observation("initial", "sensor_01", "gunshot_like_sound",
                            Position(5, 6), 1.0, 0.8)
        feed = Mock()
        feed.recent.return_value = (local,)
        agent = Mock(
            loop=asyncio.get_running_loop(), observation_feed=feed,
            created_at=1.0, informant_jid="informant@localhost", response=None,
            eligible_source_ids=("sensor_02",), max_distance=2.0,
            max_time_difference=1.0, minimum_compatible_sources=1,
            incompatibility_rules=None, compatibility_rules=None, verification_history={},
        )
        behaviour = SensorAgent.VerificationBehaviour()
        behaviour.set_agent(agent)
        behaviour.send = AsyncMock()
        calls = 0

        async def receive(timeout):
            nonlocal calls
            calls += 1
            request = parse_spade_message(behaviour.send.await_args.args[0])
            observation = model_to_dict(Observation(
                "corroborating", "sensor_02", "gunshot_like_sound",
                Position(6, 6), 1.0, 0.8,
            ))
            if calls == 1:
                observation[field] = value
            else:
                self.assertIsNone(agent.response)
                self.assertEqual(agent.verification_history, {})
            response = Message(
                "invalid-response" if calls == 1 else "valid-response",
                MessageType.VERIFY_RESPONSE, 1.0,
                {"request_message_id": request.message_id,
                 "status": "observations_available", "observations": [observation]},
                incident_id=request.incident_id, source_id="sensor_02",
                conversation_id=request.conversation_id,
            )
            incoming = build_spade_message(
                "sensor@localhost", response, performative="inform",
                conversation_id=request.conversation_id, in_reply_to=request.message_id,
            )
            incoming.sender = "informant@localhost"
            return incoming

        behaviour.receive = AsyncMock(side_effect=receive)
        await behaviour._step()
        self.assertFalse(behaviour.is_killed())
        self.assertEqual(behaviour.receive.await_count, 2)
        self.assertEqual(agent.response.message_id, "valid-response")
        self.assertEqual(agent.decision["decision"], "request_mobile_verification")
        record = next(iter(agent.verification_history[agent.conversation_id].values()))
        self.assertFalse(record["response_wait_timed_out"])
        self.assertEqual(record["rejected_responses"][0]["reason"], "invalid_response")

    async def test_sensor_processes_valid_response_after_large_intensity(self):
        await self._sensor_after_invalid_observation("intensity_score", HUGE_INTEGER)

    async def test_sensor_processes_valid_response_after_large_position(self):
        await self._sensor_after_invalid_observation("position", {"x": HUGE_INTEGER, "y": 6})


if __name__ == "__main__":
    unittest.main()

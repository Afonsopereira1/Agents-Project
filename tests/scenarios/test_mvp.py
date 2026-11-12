"""Integração local dos comportamentos SPADE e limites do movimento do MVP."""

import unittest
from dataclasses import replace
from unittest.mock import AsyncMock

from isia.communication.messages import Message, MessageType
from isia.domain.models import Mission, Position, ResourceState, ResourceStatus
from isia.reasoning.allocation import LocalResourceReservation, build_cfp_message, build_accept_message
from isia.simulation.movement import MissionExecution
from isia.simulation.world import World

try:
    from isia.simulation.runner import run_mvp
    from isia.agents.drone import DroneAgent
    from isia.agents.mobile import MobileResourceAgent
    from isia.communication.transport import build_spade_message
except ImportError:
    run_mvp = None


class TestMissionMovement(unittest.TestCase):
    def execution(self, *, energy=20.0, target=Position(3, 2), inspect=None, **options):
        reservation = LocalResourceReservation(ResourceState("patrol", "drone", Position(0, 0), True, energy))
        reservation.reserve("mission")
        mission = Mission("mission", "incident", "verify_incident", target, "mobile_verification", 0)
        return MissionExecution(reservation, mission, World(5, 5), now=0,
                                inspect=inspect or (lambda *args: "confirmed"), **options)

    def test_valid_trajectory_energy_and_return(self):
        execution = self.execution()
        positions = []
        for now in range(12):
            execution.advance(now)
            positions.append(execution.resource.position)
        self.assertEqual(positions[:6], [Position(0, 0), Position(1, 0), Position(2, 0),
                                        Position(3, 0), Position(3, 1), Position(3, 2)])
        self.assertEqual(execution.resource.position, Position(0, 0))
        self.assertEqual(execution.resource.autonomy_percent, 10)
        self.assertEqual(execution.result["completed_at"], 6)
        self.assertTrue(execution.finished)
        self.assertIsNone(execution.reservation.reserved_mission_id)

    def test_large_and_fractional_steps_have_same_result(self):
        small = self.execution(speed=2.5, energy_per_cell=0.2, service_seconds=0.5)
        large = self.execution(speed=2.5, energy_per_cell=0.2, service_seconds=0.5)
        for tick in range(51):
            small.advance(tick / 10)
        large.advance(5)
        self.assertEqual(small.resource.position, large.resource.position)
        self.assertAlmostEqual(small.resource.autonomy_percent, large.resource.autonomy_percent)
        self.assertEqual(small.result, large.result)
        times = [entry["time"] for entry in large.timeline]
        self.assertEqual(times, sorted(times))

    def test_outside_map_and_insufficient_round_trip_never_move(self):
        for options in ({"target": Position(5, 0)}, {"energy": 9}, {"energy": None}):
            with self.subTest(options=options):
                execution = self.execution(**options)
                self.assertEqual(execution.result["outcome"], "failed")
                self.assertEqual(execution.resource.position, Position(0, 0))
                self.assertIsNone(execution.reservation.reserved_mission_id)
                self.assertTrue(execution.finished)

    def test_interrupted_mission_reports_failure_and_returns(self):
        execution = self.execution()
        execution.advance(2)
        execution.interrupt()
        execution.advance(4)
        self.assertEqual(execution.result["outcome"], "failed")
        self.assertEqual(execution.resource.autonomy_percent, 16)
        self.assertEqual(execution.resource.position, Position(0, 0))
        self.assertTrue(execution.resource.available)
        self.assertIsNone(execution.reservation.reserved_mission_id)

    def test_energy_loss_marks_unavailable_and_releases_reservation(self):
        execution = self.execution()
        execution.advance(2)
        execution.reservation.update_execution("mission", replace(execution.resource, autonomy_percent=0))
        execution.interrupt("battery_failure")
        self.assertIs(execution.resource.status, ResourceStatus.UNAVAILABLE)
        self.assertEqual(execution.resource.position, Position(2, 0))
        self.assertIsNone(execution.reservation.reserved_mission_id)

    def test_return_energy_loss_is_explicit_without_changing_delivered_result(self):
        execution = self.execution()
        execution.advance(6)
        execution.reservation.update_execution("mission", replace(execution.resource, autonomy_percent=0))
        execution.advance(7)
        self.assertEqual(execution.result["outcome"], "confirmed")
        self.assertIs(execution.resource.status, ResourceStatus.UNAVAILABLE)
        self.assertIsNone(execution.reservation.reserved_mission_id)

    def test_inspector_exception_is_failure_with_return(self):
        def inspect(*args):
            raise RuntimeError("camera unavailable")
        execution = self.execution(inspect=inspect)
        execution.advance(20)
        self.assertEqual(execution.result["outcome"], "failed")
        self.assertTrue(execution.resource.available)

    def test_exact_fractional_energy_is_not_a_false_exhaustion(self):
        execution = self.execution(energy=0.6, target=Position(3, 0), energy_per_cell=0.1)
        # 2 * 3 * 0.1 e 0.6 diferem apenas por representação binária.
        for now in range(8):
            execution.advance(now)
        self.assertEqual(execution.result["outcome"], "confirmed")
        self.assertTrue(execution.resource.available)
        self.assertAlmostEqual(execution.resource.autonomy_percent, 0)

    def test_clock_cannot_go_backwards(self):
        execution = self.execution()
        execution.advance(1)
        with self.assertRaises(ValueError):
            execution.advance(0)


@unittest.skipUnless(run_mvp, "SPADE não está instalado")
class TestMVP(unittest.IsolatedAsyncioTestCase):
    async def test_alert_to_closure_two_sensors_two_candidates_and_ranger(self):
        report = await run_mvp()
        self.assertEqual(report["incident_status"], "closed")
        self.assertEqual([result["source_id"] for result in report["results"]], ["drone", "ranger"])
        proposals = [m for m in report["messages"] if m["body"]["message_type"] == "PROPOSAL"]
        self.assertEqual({m["body"]["source_id"] for m in proposals[:2]}, {"drone", "vehicle"})
        self.assertEqual(report["messages"][1]["body"]["source_id"], "sensor-2")
        self.assertEqual(report["reservations"], [None, None, None])
        self.assertTrue(all(r["available"] for r in report["resources"]))
        self.assertEqual([r["autonomy_percent"] for r in report["resources"]], [94, 100, 90])
        self.assertTrue(all(m["sender"] == "sensor-mvp@localhost" for m in report["messages"]
                            if m["body"]["message_type"] == "ACCEPT"))
        for event in ("ALERT", "corroboration", "allocating", "responding", "closed", "returning", "available"):
            self.assertIn(event, [e["event"] for e in report["timeline"]])

    async def test_not_confirmed_closes_without_ranger(self):
        report = await run_mvp(inspection_outcomes={"drone": "not_confirmed"})
        self.assertEqual(report["incident_status"], "closed")
        self.assertEqual(len(report["results"]), 1)
        self.assertEqual(report["reason"], "not_confirmed")

    async def test_inconclusive_renegotiates_with_other_patrol(self):
        report = await run_mvp(inspection_outcomes={"drone": "inconclusive"})
        self.assertEqual(report["incident_status"], "closed")
        self.assertEqual([r["source_id"] for r in report["results"]], ["drone", "vehicle", "ranger"])
        self.assertEqual(report["results"][0]["payload"]["outcome"], "inconclusive")
        self.assertEqual(report["reservations"], [None, None, None])

    async def test_exhausted_attempts_are_unresolved(self):
        report = await run_mvp(inspection_outcomes={"drone": "inconclusive", "vehicle": "failed"})
        self.assertEqual(report["incident_status"], "unresolved")
        self.assertEqual(len(report["results"]), 2)
        self.assertTrue(all(r["available"] for r in report["resources"]))

    async def test_interruption_renegotiates_and_finishes(self):
        report = await run_mvp(interrupt_resource="drone")
        self.assertEqual(report["incident_status"], "closed")
        self.assertEqual(report["results"][0]["payload"]["outcome"], "failed")
        self.assertEqual([r["source_id"] for r in report["results"]], ["drone", "vehicle", "ranger"])
        self.assertEqual(report["reservations"], [None, None, None])

    async def test_ranger_failure_does_not_close_as_success(self):
        report = await run_mvp(inspection_outcomes={"ranger": "failed"})
        self.assertEqual(report["incident_status"], "unresolved")
        self.assertEqual(report["reason"], "failed")

    async def test_result_contract_rejects_malformed_outcome_and_chronology(self):
        report = await run_mvp()
        result = report["results"][0]
        for patch in ({"outcome": "success"}, {"completed_at": -1},
                      {"completed_at": result["created_at"] + 1}, {"resource_id": "foreign"}):
            changed = {**result, "payload": {**result["payload"], **patch}}
            with self.assertRaises(ValueError):
                Message.from_dict(changed)

    async def test_completed_accept_cannot_reserve_again_even_with_new_id(self):
        agent = DroneAgent("drone@localhost", "test", ResourceState("drone", "drone", Position(0, 0), True, 20),
                           ("mobile_verification",), minimum_autonomy_percent=1,
                           eta_seconds=0, energy_cost_percent=0, load=0)
        agent.configure_execution(World(5, 5), lambda *args: "confirmed")
        mission = Mission("m", "i", "verify_incident", Position(1, 0), "mobile_verification", 0)
        cfp = build_cfp_message(mission, 0, 10)
        proposal = agent.evaluate_request(cfp)
        accept = build_accept_message(cfp, proposal, 0)
        agent._proposal_context[proposal.message_id] = (cfp, proposal, "sensor@localhost")
        agent.reservation.reserve("m")
        agent.start_execution(cfp, accept, "sensor@localhost")
        execution = MobileResourceAgent.ExecutionBehaviour()
        execution.set_agent(agent)
        execution.send = AsyncMock(side_effect=[OSError("transport failure"), None])
        agent.set_simulated_time(2)
        with self.assertLogs("isia.agents.mobile", level="WARNING"):
            await execution.run()
        first_body = execution.send.await_args_list[0].args[0].body
        agent.set_simulated_time(3)
        await execution.run()
        await execution.run()
        self.assertEqual(execution.send.await_count, 2)
        self.assertEqual(execution.send.await_args_list[1].args[0].body, first_body)
        self.assertIsNone(agent.reservation.reserved_mission_id)
        for accept_id in (accept.message_id, "another-accept"):
            replay = Message.from_dict({**accept.to_dict(), "message_id": accept_id})
            incoming = build_spade_message(str(agent.jid), replay, performative="accept-proposal",
                                           conversation_id=cfp.conversation_id,
                                           in_reply_to=proposal.message_id, protocol="contract-net")
            incoming.sender = "sensor@localhost"
            behaviour = MobileResourceAgent.AcceptBehaviour()
            behaviour.set_agent(agent)
            behaviour.receive, behaviour.send = AsyncMock(return_value=incoming), AsyncMock()
            await behaviour.run()
            self.assertIsNone(agent.reservation.reserved_mission_id)
            self.assertEqual(len(agent.executions), 1)

    async def test_result_rejects_wrong_sender_conversation_task_and_stale_completion(self):
        from isia.agents.incident import IncidentSensorAgent
        agent = IncidentSensorAgent("sensor@localhost", "test", "peer@localhost")
        agent.configure_mvp({}, {}, receive_timeout=0.01)
        agent.simulated_time = 5
        mission = Mission("m", "i", "verify_incident", Position(1, 0), "mobile_verification", 0)
        accept = Message("accept", MessageType.ACCEPT, 2, {}, mission_id="m", incident_id="i", conversation_id="c")
        base = dict(message_id="result", message_type=MessageType.MISSION_RESULT, created_at=4,
                    payload={"accept_message_id": "accept", "outcome": "confirmed", "resource_id": "drone",
                             "task": "verify_incident", "reason": "inspection", "completed_at": 4},
                    mission_id="m", incident_id="i", source_id="drone", conversation_id="c")
        for changes, sender in (({}, "foreign@localhost"), ({"conversation_id": "other"}, "drone@localhost"),
                                ({"payload": {**base["payload"], "task": "respond_incident"}}, "drone@localhost"),
                                ({"payload": {**base["payload"], "completed_at": 1}}, "drone@localhost")):
            body = Message(**{**base, **changes})
            incoming = build_spade_message(str(agent.jid), body, performative="inform",
                                           conversation_id=body.conversation_id,
                                           in_reply_to="accept", protocol="contract-net")
            incoming.sender = sender
            behaviour = agent.IncidentBehaviour()
            behaviour.set_agent(agent)
            behaviour.receive = AsyncMock(side_effect=[incoming, None])
            result = await behaviour.mission_result(("drone@localhost", accept, "drone"), mission)
            self.assertIsNone(result)
            self.assertEqual(agent.results, [])

    async def test_mobile_rejects_impossible_target_and_round_trip_energy(self):
        agent = DroneAgent("drone@localhost", "test", ResourceState("drone", "drone", Position(0, 0), True, 5),
                           ("mobile_verification",), minimum_autonomy_percent=1,
                           eta_seconds=0, energy_cost_percent=0, load=0)
        agent.configure_execution(World(5, 5), lambda *args: "confirmed")
        for target, reason in ((Position(5, 0), "target_outside_map"),
                               (Position(3, 0), "autonomy_insufficient")):
            cfp = build_cfp_message(Mission("m", "i", "verify_incident", target, "mobile_verification", 0), 0, 10)
            response = agent.evaluate_request(cfp)
            self.assertIs(response.message_type, MessageType.REJECT)
            self.assertEqual(response.payload["reason"], reason)

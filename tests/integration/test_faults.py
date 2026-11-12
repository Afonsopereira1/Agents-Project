"""Etapa 8: falhas injetadas no transporte local terminam em estados explícitos."""

import json
from pathlib import Path
import unittest
from unittest.mock import patch

try:
    from isia.simulation.runner import run_mvp, fault_settings
except ImportError:
    run_mvp = None


def executions(report, resource_id):
    # Entradas da execução móvel trazem posição; as do sensor não.
    return [e for e in report["timeline"] if e["event"] == "reserved"
            and e["resource_id"] == resource_id and "position" in e]


@unittest.skipUnless(run_mvp, "SPADE não está instalado")
class TestFaults(unittest.IsolatedAsyncioTestCase):
    async def test_lost_cfp_is_unresolved_without_reservations(self):
        report = await run_mvp(faults={"drop": ["CFP"]})
        self.assertEqual((report["incident_status"], report["reason"]),
                         ("unresolved", "no_eligible_proposals"))
        self.assertEqual(report["reservations"], [None, None, None])
        self.assertEqual(report["missions"], [])

    async def test_lost_accept_is_unresolved_and_reserves_nothing(self):
        report = await run_mvp(faults={"drop": ["ACCEPT"]})
        self.assertEqual((report["incident_status"], report["reason"]),
                         ("unresolved", "confirmation_unknown"))
        self.assertEqual(report["reservations"], [None, None, None])

    async def test_lost_mission_result_keeps_incident_open_and_resource_returns(self):
        report = await run_mvp(faults={"drop": ["MISSION_RESULT"]}, max_seconds=15)
        self.assertEqual((report["incident_status"], report["reason"]),
                         ("unresolved", "mission_result_unknown"))
        self.assertEqual(report["reservations"], [None, None, None])
        self.assertTrue(all(r["available"] for r in report["resources"]))

    async def test_duplicated_result_and_accept_have_single_effect(self):
        report = await run_mvp(faults={"duplicate": ["MISSION_RESULT", "ACCEPT"]})
        self.assertEqual(report["incident_status"], "closed")
        self.assertEqual([r["source_id"] for r in report["results"]], ["drone", "ranger"])
        self.assertEqual(len(report["missions"]), 2)
        self.assertEqual(len(executions(report, "drone")), 1)
        self.assertEqual(len(executions(report, "ranger")), 1)

    async def test_late_proposals_are_ignored_and_short_delay_is_tolerated(self):
        late = await run_mvp(faults={"delay": {"PROPOSAL": 1.0}})
        self.assertEqual((late["incident_status"], late["reason"]), ("unresolved", "no_eligible_proposals"))
        short = await run_mvp(faults={"delay": {"CFP": 0.05, "PROPOSAL": 0.05}})
        self.assertEqual(short["incident_status"], "closed")

    async def test_unavailable_patrol_uses_other_and_no_patrol_is_unresolved(self):
        report = await run_mvp(faults={"unavailable_agents": ["drone-mvp"]})
        self.assertEqual([r["source_id"] for r in report["results"]], ["vehicle", "ranger"])
        report = await run_mvp(faults={"unavailable_agents": ["drone-mvp", "vehicle-mvp"]})
        self.assertEqual((report["incident_status"], report["reason"]),
                         ("unresolved", "no_eligible_proposals"))

    async def test_unavailable_peer_sensor_ends_without_hanging(self):
        with patch("isia.agents.sensor.RESPONSE_TIMEOUT_SECONDS", 0.2):
            report = await run_mvp(faults={"unavailable_agents": ["sensor-peer-mvp"]})
        self.assertEqual((report["incident_status"], report["decision"]["reason"]), ("expired", "timeout"))
        self.assertTrue(all(f["fault"] == "lost" for f in report["fault_log"]))

    async def test_resource_occupied_after_proposal_renegotiates_once(self):
        report = await run_mvp(faults={"occupied_after_proposal": ["drone"]})
        self.assertEqual(report["incident_status"], "closed")
        self.assertEqual([r["source_id"] for r in report["results"]], ["vehicle", "ranger"])
        self.assertEqual(executions(report, "drone"), [])
        self.assertEqual(report["reservations"][0], "external-mission")

    async def test_total_loss_ends_explicitly_and_records_seed(self):
        with patch("isia.agents.sensor.RESPONSE_TIMEOUT_SECONDS", 0.2):
            report = await run_mvp(faults={"loss": 1.0, "seed": 3})
        self.assertIn(report["incident_status"], ("expired", "unresolved"))
        self.assertEqual(report["missions"], [])
        self.assertEqual((report["faults"]["seed"], report["scenario_seed"]), (3, 6))

    async def test_example_fault_file_is_valid(self):
        root = Path(__file__).resolve().parents[2]
        self.assertIsNotNone(fault_settings(json.loads((root / "config/faults.json").read_text())))

    def test_invalid_fault_settings_are_rejected(self):
        for faults in ({"loss": 2}, {"unknown": 1}, {"seed": "1"}, {"delay": {"CFP": -1}},
                       {"drop": "CFP"}):
            with self.assertRaises(ValueError):
                fault_settings(faults)


if __name__ == "__main__":
    unittest.main()

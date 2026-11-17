"""Bloco F2: iniciadores e patrulhas adicionais no runner (extra_initiators, extra_patrols, cfp_limit)."""

import json
from pathlib import Path
import unittest

try:
    from isia.domain.models import Position
    from isia.simulation.runner import run_mvp
except ImportError:
    run_mvp = None


def executions(report, resource_id):
    # Entradas da execução móvel trazem posição; as do sensor não.
    return [e for e in report["timeline"] if e["event"] == "reserved"
            and e["resource_id"] == resource_id and "position" in e]


@unittest.skipUnless(run_mvp, "SPADE não está instalado")
class TestStressExtensions(unittest.IsolatedAsyncioTestCase):
    async def test_two_initiators_share_resources_without_double_booking(self):
        root = Path(__file__).resolve().parents[2]
        settings = json.loads((root / "config/scenarios/A.json").read_text())["response_settings"]
        settings["policy"].update(patrol_threshold=0.01, severe_patrol_threshold=0.01)
        settings["sources"]["sensor-3"] = {"modality": "acoustic", "correlation_group": "local_3"}
        near = {"kind": "acoustic", "detection_range": 1.0}
        threat = {"kind": "threat", "starts_at": 0.0, "duration": 1000.0}
        report = await run_mvp(
            response_settings=settings, corroborate=False, extra_initiators={"sensor-3": Position(6, 2)},
            scenario={"run_id": "two", "seed": 1, "resources": {},
                      "sources": {"sensor-1": near, "sensor-2": {"kind": "visual", "detection_range": 0.0},
                                  "sensor-3": near},
                      "events": [{**threat, "event_id": "a", "position": {"x": 2, "y": 2}},
                                 {**threat, "event_id": "b", "position": {"x": 6, "y": 2}}]})
        other = report["extra_initiators"]["sensor-3"]
        # Duas patrulhas chegam para as duas verificações; o único guarda só serve uma ocorrência.
        self.assertEqual([len(executions(report, r)) for r in ("drone", "vehicle", "ranger")], [1, 1, 1])
        self.assertEqual(sorted((report["incident_status"], other["incident_status"])),
                         ["closed", "unresolved"])
        self.assertEqual(report["reservations"], [None, None, None])
        with self.assertRaises(ValueError):
            await run_mvp(extra_initiators={"sensor-1": Position(0, 0)})

    async def test_cfp_limit_keeps_messages_constant_with_more_patrols(self):
        extra = {f"drone-{i}": Position(7, i) for i in range(2, 8)}
        base = await run_mvp()
        every = await run_mvp(extra_patrols=extra)
        nearest = await run_mvp(extra_patrols=extra, cfp_limit=2)
        count = lambda report: sum(m["body"]["message_type"] == "CFP" for m in report["messages"])
        # 6 patrulhas a mais: 6 CFP a mais sem limite, nenhum com K=2; a decisão não muda.
        self.assertEqual((count(base), count(every), count(nearest)), (3, 9, 3))
        self.assertEqual({r["incident_status"] for r in (base, every, nearest)}, {"closed"})
        self.assertEqual(len(nearest["messages"]), len(base["messages"]))
        for invalid in ({"extra_patrols": {"drone": Position(0, 0)}}, {"cfp_limit": 0}):
            with self.assertRaises(ValueError):
                await run_mvp(**invalid)

    async def test_dynamic_deadline_survives_slow_proposals(self):
        slow = {"delay": {"PROPOSAL": 0.6}}
        fixed = await run_mvp(faults=slow)
        dynamic = await run_mvp(faults=slow, max_receive_timeout=2.0)
        # Propostas a 0,6 s: o prazo fixo de 0,5 s desiste; o dinâmico espera porque não tem nenhuma.
        self.assertEqual((fixed["incident_status"], fixed["reason"]), ("unresolved", "no_eligible_proposals"))
        self.assertEqual(dynamic["incident_status"], "closed")
        with self.assertRaises(ValueError):
            await run_mvp(max_receive_timeout=0.1)

    async def two_threats(self, **options):
        """Duas ocorrências ao mesmo tempo (sensor-1 e sensor-3) e um só guarda, com fila."""
        root = Path(__file__).resolve().parents[2]
        settings = json.loads((root / "config/scenarios/A.json").read_text())["response_settings"]
        settings["policy"].update(patrol_threshold=0.01, severe_patrol_threshold=0.01)
        settings["sources"]["sensor-3"] = {"modality": "acoustic", "correlation_group": "local_3"}
        settings.update(options.pop("settings", {}))
        near = {"kind": "acoustic", "detection_range": 1.0}
        threat = {"kind": "threat", "starts_at": 0.0, "duration": 1000.0}
        report = await run_mvp(
            response_settings=settings, corroborate=False, extra_initiators={"sensor-3": Position(6, 2)},
            queue_rounds=20, max_seconds=30.0, **options,
            scenario={"run_id": "queue", "seed": 1, "resources": {},
                      "sources": {"sensor-1": near, "sensor-2": {"kind": "visual", "detection_range": 0.0},
                                  "sensor-3": near},
                      "events": [{**threat, "event_id": "a", "position": {"x": 2, "y": 2}},
                                 {**threat, "event_id": "b", "position": {"x": 6, "y": 2}}]})
        closed_at = {e.get("initiator", "sensor-1"): e["time"] for e in report["timeline"]
                     if e["event"] == "INCIDENT_CLOSED"}
        return report, closed_at

    async def test_queue_closes_both_incidents_with_one_ranger(self):
        report, closed_at = await self.two_threats()
        # Sem fila, a segunda ocorrência fica unresolved (primeiro teste); com fila, espera pelo guarda.
        self.assertEqual((report["incident_status"], report["extra_initiators"]["sensor-3"]["incident_status"]),
                         ("closed", "closed"))
        self.assertEqual(len(executions(report, "ranger")), 2)
        self.assertLess(closed_at["sensor-1"], closed_at["sensor-3"])
        with self.assertRaises(ValueError):
            await run_mvp(queue_rounds=-1)

    async def test_queue_priority_serves_the_severe_incident_first(self):
        severe = {"severity_by_source": {"sensor-1": 0.2, "sensor-3": 0.9}}
        report, closed_at = await self.two_threats(queue_priority=True, settings=severe)
        self.assertEqual((report["incident_status"], report["extra_initiators"]["sensor-3"]["incident_status"]),
                         ("closed", "closed"))
        # A mesma disputa do teste anterior, mas a ocorrência grave (sensor-3) passa à frente.
        self.assertLess(closed_at["sensor-3"], closed_at["sensor-1"])
        priorities = {m["sender"]: m["body"]["payload"]["priority"] for m in report["messages"]
                      if m["body"]["message_type"] == "CFP"}
        self.assertEqual(priorities, {"sensor-mvp@localhost": 0, "sensor-3-mvp@localhost": 2})
        self.assertEqual(report["reservations"], [None, None, None])

    async def test_silent_invalid_stops_replies_to_incoherent_accepts(self):
        replies = lambda report: sum("junk-" in str(m["body"]) and m["body"]["message_type"] == "STATUS"
                                     for m in report["messages"])
        loud = await run_mvp(faults={"flood": 2})
        quiet = await run_mvp(faults={"flood": 2}, silent_invalid=True)
        # Dois ACCEPT reais (patrulha e guarda), duas variantes de lixo cada, flood 2: 8 respostas.
        self.assertEqual((replies(loud), replies(quiet)), (8, 0))
        self.assertEqual((loud["incident_status"], quiet["incident_status"]), ("closed", "closed"))


if __name__ == "__main__":
    unittest.main()

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


if __name__ == "__main__":
    unittest.main()

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
            queue_rounds=0,
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
        fixed = await run_mvp(faults=slow, max_receive_timeout=None)
        dynamic = await run_mvp(faults=slow)  # teto de 2,0 s por omissão
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
        threat = {"kind": "threat", "starts_at": 0.0, "duration": options.pop("duration", 1000.0)}
        report = await run_mvp(
            response_settings=settings, corroborate=False, extra_initiators={"sensor-3": Position(6, 2)},
            queue_rounds=20, max_seconds=30.0,
            scenario={"run_id": "queue", "seed": 1, "resources": options.pop("resources", {}),
                      "sources": {"sensor-1": near, "sensor-2": {"kind": "visual", "detection_range": 0.0},
                                  "sensor-3": near},
                      "events": [{**threat, "event_id": "a", "position": {"x": 2, "y": 2}},
                                 {**threat, "event_id": "b", "position": {"x": 6, "y": 2}}]}, **options)
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
        loud = await run_mvp(faults={"flood": 2}, silent_invalid=False)
        quiet = await run_mvp(faults={"flood": 2})  # silêncio por omissão
        # Dois ACCEPT reais (patrulha e guarda), duas variantes de lixo cada, flood 2: 8 respostas.
        self.assertEqual((replies(loud), replies(quiet)), (8, 0))
        self.assertEqual((loud["incident_status"], quiet["incident_status"]), ("closed", "closed"))

    def statuses(self, report):
        return sorted((report["incident_status"], report["extra_initiators"]["sensor-3"]["incident_status"]))

    async def test_late_ranger_does_not_confirm_and_validity_expires_instead(self):
        # Ameaças de 16 s e guarda longe, em (7,7): chega à primeira aos 14 s e só fica livre aos 24 s.
        far = {"duration": 16.0, "resources": {"ranger": {"position": {"x": 7, "y": 7}}}}
        late, _ = await self.two_threats(**far)
        outcomes = [r["payload"]["outcome"] for v in (late, late["extra_initiators"]["sensor-3"])
                    for r in v["results"] if r["payload"]["task"] == "respond_incident"]
        self.assertEqual(sorted(outcomes), ["confirmed", "not_confirmed"])
        # Com prazo de validade, quem espera na fila deixa de ver a ameaça e não manda o guarda.
        report, _ = await self.two_threats(**far, expire_unseen=True)
        self.assertEqual(self.statuses(report), ["closed", "expired"])
        self.assertEqual(len(executions(report, "ranger")), 1)
        self.assertIn("threat_expired", (report["reason"], report["extra_initiators"]["sensor-3"]["reason"]))

    async def test_extra_ranger_serves_the_second_incident(self):
        report, _ = await self.two_threats(extra_rangers={"ranger-2": Position(6, 4)})
        self.assertEqual(self.statuses(report), ["closed", "closed"])
        self.assertEqual([len(executions(report, r)) for r in ("ranger", "ranger-2")], [1, 1])
        self.assertEqual(report["reservations"], [None] * 4)
        with self.assertRaises(ValueError):
            await run_mvp(extra_rangers={"ranger": Position(0, 0)})

    async def test_busy_refusal_says_when_the_resource_is_free(self):
        report, _ = await self.two_threats(queue_until_free=True)
        busy = [m["body"] for m in report["messages"] if m["body"]["payload"].get("busy_until") is not None]
        self.assertTrue(busy)
        self.assertTrue(all(b["message_type"] == "REJECT" and b["payload"]["busy_until"] > b["created_at"]
                            for b in busy))
        self.assertEqual(self.statuses(report), ["closed", "closed"])

    async def test_chained_mission_starts_on_the_way_back(self):
        report, _ = await self.two_threats(chain_missions=True)
        starts = [e["position"] for e in executions(report, "ranger")]
        # A segunda missão do guarda parte do caminho de regresso, não da base (5,5).
        self.assertEqual((len(starts), starts[0]), (2, {"x": 5, "y": 5}))
        self.assertNotEqual(starts[1], {"x": 5, "y": 5})
        self.assertEqual(self.statuses(report), ["closed", "closed"])
        self.assertEqual(report["resources"][2]["position"], {"x": 5, "y": 5})
        self.assertEqual(report["reservations"], [None, None, None])

    async def test_extra_informant_corroborates_the_extra_initiator(self):
        root = Path(__file__).resolve().parents[2]
        settings = json.loads((root / "config/scenarios/A.json").read_text())["response_settings"]
        settings["sources"].update({"sensor-3": {"modality": "acoustic", "correlation_group": "local_3"},
                                    "sensor-4": {"modality": "visual", "correlation_group": "camera_4"}})
        near = {"kind": "acoustic", "detection_range": 1.0}
        blind = {"kind": "visual", "detection_range": 0.0}
        scenario = {"run_id": "informant", "seed": 1, "resources": {},
                    "sources": {"sensor-1": near, "sensor-2": blind, "sensor-3": near,
                                "sensor-4": {"kind": "visual", "detection_range": 1.0}},
                    "events": [{"kind": "threat", "starts_at": 0.0, "duration": 1000.0, "event_id": "b",
                                "position": {"x": 6, "y": 2}}]}
        common = dict(response_settings=settings, extra_initiators={"sensor-3": Position(6, 2)},
                      scenario=scenario, max_seconds=30.0)
        own = await run_mvp(extra_informants={"sensor-4": Position(7, 2)}, **common)
        decision = own["extra_initiators"]["sensor-3"]["decision"]
        self.assertEqual((decision["decision"], list(decision["compatible_source_ids"])),
                         ("request_mobile_verification", ["sensor-4"]))
        self.assertEqual(own["extra_initiators"]["sensor-3"]["incident_status"], "closed")
        # Só com o sensor-2 (cego para esta célula), a mesma ocorrência não é corroborada.
        scenario["sources"].pop("sensor-4")
        shared = await run_mvp(extra_informants={}, **common)
        self.assertEqual(shared["extra_initiators"]["sensor-3"]["incident_status"], "expired")

    async def test_retransmit_recovers_lost_replies(self):
        resent = lambda report: len(report["messages"]) - len(
            {(m["to"], m["body"]["message_id"]) for m in report["messages"]})
        base = await run_mvp()
        self.assertEqual(resent(base), 0)
        # As primeiras mensagens de cada tipo perdem-se sempre (as duas propostas das patrulhas);
        # só o reenvio as recupera. Sem reenvio, perder o VERIFY_RESPONSE custa 10 s reais: não se repete aqui.
        for kind, count, reason in (("PROPOSAL", 2, "no_eligible_proposals"), ("STATUS", 1, "confirmation_unknown"),
                                    ("VERIFY_RESPONSE", 1, None)):
            with self.subTest(kind=kind):
                again = await self.drop_first(kind, count, retransmit=1)
                if reason is not None:
                    lost = await self.drop_first(kind, count, retransmit=0)
                    self.assertEqual((lost["incident_status"], lost["reason"]), ("unresolved", reason))
                self.assertEqual((again["incident_status"], again["reason"]), ("closed", "confirmed"))
                self.assertGreaterEqual(resent(again), 1)
                self.assertEqual(again["reservations"], [None, None, None])
        with self.assertRaises(ValueError):
            await run_mvp(retransmit=-1)

    async def drop_first(self, kind, count, **options):
        """Correr o MVP perdendo as primeiras ``count`` mensagens do tipo indicado."""
        from isia.simulation import runner
        original, dropped = runner.fault_settings, []

        class OnceList(list):
            def __contains__(self, value):
                if value != kind or len(dropped) >= count:
                    return False
                dropped.append(value)
                return True

        def patched(faults):
            settings = original(faults)
            settings["drop"] = OnceList()
            return settings
        runner.fault_settings = patched
        try:
            return await run_mvp(faults={}, receive_timeout=0.2, max_receive_timeout=0.2, **options)
        finally:
            runner.fault_settings = original

    async def test_alert_makes_one_of_two_overlapping_initiators_yield(self):
        root = Path(__file__).resolve().parents[2]
        settings = json.loads((root / "config/scenarios/A.json").read_text())["response_settings"]
        settings["policy"].update(patrol_threshold=0.01, severe_patrol_threshold=0.01)
        settings["sources"]["sensor-3"] = {"modality": "acoustic", "correlation_group": "local_3"}
        hear = {"kind": "acoustic", "detection_range": 1.5}
        threat = {"kind": "threat", "starts_at": 0.0, "duration": 1000.0}

        async def run(events, **options):
            return await run_mvp(
                response_settings=settings, corroborate=False, extra_initiators={"sensor-3": Position(4, 2)},
                scenario={"run_id": "alert", "seed": 1, "resources": {},
                          "sources": {"sensor-1": hear, "sensor-2": {"kind": "visual", "detection_range": 0.0},
                                      "sensor-3": hear},
                          "events": [{**threat, **event} for event in events]}, **options)
        shared = [{"event_id": "a", "position": {"x": 3, "y": 2}}]
        reasons = lambda report: sorted((report["reason"], report["extra_initiators"]["sensor-3"]["reason"]))
        # Sem aviso, os dois iniciadores tratam a mesma ameaça: duas idas de patrulha para um caçador.
        twice = await run(shared)
        self.assertEqual(reasons(twice), ["confirmed", "confirmed"])
        once = await run(shared, alert_distance=1.0)
        self.assertEqual(reasons(once), ["confirmed", "duplicate_alert"])
        self.assertEqual(sum(m["body"]["message_type"] == "ALERT" for m in once["messages"]), 2)
        self.assertLess(sum(m["body"]["message_type"] == "CFP" for m in once["messages"]),
                        sum(m["body"]["message_type"] == "CFP" for m in twice["messages"]))
        # Duas ameaças a três células uma da outra não se fundem: cada iniciador trata a sua.
        apart = await run([{"event_id": "a", "position": {"x": 1, "y": 2}},
                           {"event_id": "b", "position": {"x": 5, "y": 2}}], alert_distance=1.0)
        self.assertNotIn("duplicate_alert", reasons(apart))

    async def test_map_and_sensor_positions_come_from_arguments(self):
        report = await run_mvp(map_size=(10, 6), sensor_positions={"sensor-2": Position(3, 2)})
        self.assertEqual(report["world"], {"width": 10, "height": 6, "sensors": {
            "sensor-1": {"x": 2, "y": 2}, "sensor-2": {"x": 3, "y": 2}}})
        self.assertEqual(report["incident_status"], "closed")
        with self.assertRaises(ValueError):
            await run_mvp(sensor_positions={"sensor-9": Position(0, 0)})


if __name__ == "__main__":
    unittest.main()

"""Etapa 9: métricas com contagens conhecidas e denominadores zero."""

import unittest

from isia.evaluation.metrics import confusion, rates, run_metrics, summarize


def report(threat=True, decision="request_mobile_verification", results=(), faults=()):
    return {
        "ground_truth": {"events": [{"is_threat": threat}], "observations": {}},
        "decision": None if decision is None else {"decision": decision},
        "results": [{"payload": payload} for payload in results],
        "initial_resources": [{"resource_id": "drone", "autonomy_percent": 100.0},
                              {"resource_id": "ranger", "autonomy_percent": 100.0}],
        "resources": [{"resource_id": "drone", "autonomy_percent": 94.0},
                      {"resource_id": "ranger", "autonomy_percent": 90.0}],
        "fault_log": [{"fault": fault} for fault in faults],
        "missions": [{"status": "done"}, {"status": "failed"}],
        "incident_status": "closed", "reason": "confirmed",
        "timeline": [{"event": "ALERT", "time": 0.0},
                     {"event": "reserved", "time": 0.0, "resource_id": "drone", "position": {}}],
        "messages": [{}, {}, {}],
    }


class TestMetrics(unittest.TestCase):
    def test_confusion_counts_known_pairs(self):
        counts = confusion([(True, True), (True, False), (False, True), (False, False), (False, False)])
        self.assertEqual(counts, {"TP": 1, "FP": 1, "TN": 2, "FN": 1})
        self.assertEqual(rates(counts), {"precision": 0.5, "recall": 0.5, "fpr": 1 / 3, "accuracy": 0.6})

    def test_zero_denominators_are_none(self):
        self.assertEqual(rates(confusion([])), {"precision": None, "recall": None, "fpr": None, "accuracy": None})
        # Só negativos corretamente ignorados: sem positivos previstos nem reais.
        values = rates(confusion([(False, False)]))
        self.assertIsNone(values["precision"])
        self.assertIsNone(values["recall"])
        self.assertEqual(values["fpr"], 0.0)

    def test_run_metrics_from_report(self):
        metrics = run_metrics(report(results=[
            {"task": "verify_incident", "outcome": "confirmed", "completed_at": 4.0},
            {"task": "respond_incident", "outcome": "confirmed", "completed_at": 10.0},
        ], faults=["lost", "duplicated", "duplicated"]))
        self.assertTrue(metrics["threat"] and metrics["dispatched"] and metrics["confirmed"])
        self.assertEqual((metrics["verification_time"], metrics["response_time"]), (4.0, 10.0))
        self.assertEqual(metrics["energy_used"], 16.0)
        self.assertEqual((metrics["messages_sent"], metrics["messages_lost"],
                          metrics["messages_duplicated"]), (3, 1, 2))
        self.assertEqual((metrics["missions_done"], metrics["missions_failed"]), (1, 1))
        self.assertEqual(metrics["first_patrol"], "drone")

    def test_run_without_events_or_alert(self):
        empty = report(decision=None)
        empty["ground_truth"]["events"] = []
        metrics = run_metrics(empty)
        self.assertFalse(metrics["threat"] or metrics["dispatched"])
        self.assertIsNone(metrics["verification_time"])
        summary = summarize([metrics])
        self.assertEqual((summary["TN"], summary["precision"], summary["recall"]), (1, None, None))
        self.assertEqual(summary["verification_time"], {"n": 0, "mean": None, "median": None, "stdev": None})


if __name__ == "__main__":
    unittest.main()

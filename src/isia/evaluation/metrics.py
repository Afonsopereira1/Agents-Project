"""Métricas da Etapa 9, calculadas só pelo avaliador a partir do relatório de run_mvp.

Unidade de avaliação: uma execução = uma zona (o mapa do MVP) numa janela única.
Positivo real: existe pelo menos um evento ``threat`` no cenário.
Positivo previsto: a política mobiliza recursos (patrulha ou guardas).
Denominador zero devolve ``None`` (``N/A``), nunca 0 ou 1.
"""

from statistics import mean, median, stdev

from isia.reasoning.allocation import RANGER_DECISION, RANGER_TASK


DISPATCH = {"request_mobile_verification", RANGER_DECISION}
NUMERIC = ("verification_time", "response_time", "energy_used", "messages_sent",
           "messages_lost", "messages_duplicated", "missions_done", "missions_failed")


def ratio(numerator, denominator):
    return None if denominator == 0 else numerator / denominator


def confusion(pairs):
    """``pairs`` = iterável de (real, previsto) booleanos."""
    counts = {"TP": 0, "FP": 0, "TN": 0, "FN": 0}
    for truth, predicted in pairs:
        counts[("T" if truth == predicted else "F") + ("P" if predicted else "N")] += 1
    return counts


def rates(counts):
    tp, fp, tn, fn = (counts[key] for key in ("TP", "FP", "TN", "FN"))
    return {"precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn),
            "fpr": ratio(fp, fp + tn), "accuracy": ratio(tp + tn, tp + fp + tn + fn)}


def run_metrics(report):
    truth = any(event["is_threat"] for event in report["ground_truth"]["events"])
    decision = (report["decision"] or {}).get("decision")
    results = [result["payload"] for result in report["results"]]
    verify = [r["completed_at"] for r in results if r["task"] == "verify_incident"]
    respond = [r["completed_at"] for r in results if r["task"] == RANGER_TASK]
    initial = {r["resource_id"]: r["autonomy_percent"] for r in report["initial_resources"]}
    faults = [entry["fault"] for entry in report["fault_log"]]
    statuses = [mission["status"] for mission in report["missions"]]
    return {
        "threat": truth,
        "alert": any(entry["event"] == "ALERT" for entry in report["timeline"]),
        "dispatched": decision in DISPATCH,
        "decision": decision,
        "confirmed": any(r["task"] == "verify_incident" and r["outcome"] == "confirmed" for r in results),
        "status": report["incident_status"],
        "reason": report["reason"],
        "unresolved": report["incident_status"] == "unresolved",
        # Segundos simulados desde t=0 (início dos eventos e do alerta nesta janela única).
        "verification_time": min(verify) if verify else None,
        "response_time": min(respond) if respond else None,
        "energy_used": sum(initial[r["resource_id"]] - r["autonomy_percent"] for r in report["resources"]),
        "messages_sent": len(report["messages"]),
        "messages_lost": faults.count("lost"),
        "messages_duplicated": faults.count("duplicated"),
        "missions_done": statuses.count("done"),
        "missions_failed": statuses.count("failed"),
        # Entradas de execução móvel trazem posição; as do sensor não.
        "first_patrol": next((e["resource_id"] for e in report["timeline"]
                              if e["event"] == "reserved" and "position" in e
                              and e["resource_id"] != "ranger"), None),
    }


def describe(values):
    values = [value for value in values if value is not None]
    if not values:
        return {"n": 0, "mean": None, "median": None, "stdev": None}
    return {"n": len(values), "mean": mean(values), "median": median(values),
            "stdev": stdev(values) if len(values) > 1 else None}


def summarize(rows):
    """Agrega linhas de run_metrics de um mesmo cenário/variante."""
    counts = confusion((row["threat"], row["dispatched"]) for row in rows)
    return {"runs": len(rows), **counts, **rates(counts),
            "confirmed_runs": sum(row["confirmed"] for row in rows),
            "unresolved_runs": sum(row["unresolved"] for row in rows),
            **{name: describe(row[name] for row in rows) for name in NUMERIC}}

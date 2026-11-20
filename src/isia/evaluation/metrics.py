"""Métricas da Etapa 9, calculadas só pelo avaliador a partir do relatório de run_mvp.

Unidade de avaliação: uma execução = uma zona (o mapa do MVP) numa janela única.
Positivo real: existe pelo menos um evento ``threat`` no cenário.
Positivo previsto: a política mobiliza recursos (patrulha ou guardas).
Denominador zero devolve ``None`` (``N/A``), nunca 0 ou 1.
Energia desconhecida em qualquer recurso torna o consumo total indisponível.
As contagens de missões incluem apenas estados conhecidos pelo coordenador;
conclusões locais cujo resultado não chegou não são contadas como conhecidas.
Com vários iniciadores, verdade global e decisão de sensor-1 não têm o mesmo
âmbito: summarize devolve None nas oito métricas de classificação. Os campos
individuais de run_metrics mantêm-se para diagnóstico; não medem todas as ameaças.
"""

from statistics import mean, median, stdev

from isia.reasoning.allocation import RANGER_DECISION, RANGER_TASK


DISPATCH = {"request_mobile_verification", RANGER_DECISION}
NUMERIC = ("verification_time", "response_time", "energy_used", "messages_sent",
           "messages_lost", "messages_duplicated", "missions_done", "missions_failed")


def ratio(numerator, denominator):
    """Dividir numerador por denominador; denominador zero devolve None (N/A).

    Args:
        numerator (int | float): Numerador.
        denominator (int | float): Denominador.

    Returns:
        float | None: O quociente, ou ``None`` se o denominador for zero.
    """
    return None if denominator == 0 else numerator / denominator


def confusion(pairs):
    """Contar a matriz de confusão.

    Args:
        pairs (Iterable[tuple[bool, bool]]): Pares (real, previsto) de cada execução.

    Returns:
        dict[str, int]: Contagens com as chaves ``TP``, ``FP``, ``TN`` e ``FN``.
    """
    counts = {"TP": 0, "FP": 0, "TN": 0, "FN": 0}
    for truth, predicted in pairs:
        counts[("T" if truth == predicted else "F") + ("P" if predicted else "N")] += 1
    return counts


def rates(counts):
    """Calcular precision, recall, fpr e accuracy; denominador zero dá None.

    Args:
        counts (dict[str, int]): Matriz de confusão, como a devolvida por ``confusion``.

    Returns:
        dict[str, float | None]: ``precision``, ``recall``, ``fpr`` e ``accuracy``, em [0, 1].
    """
    tp, fp, tn, fn = (counts[key] for key in ("TP", "FP", "TN", "FN"))
    return {"precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn),
            "fpr": ratio(fp, fp + tn), "accuracy": ratio(tp + tn, tp + fp + tn + fn)}


def run_metrics(report):
    """Extrair as métricas de uma execução a partir do relatório de run_mvp.

    ``threat`` vem apenas de ground_truth e ``dispatched`` da decisão no topo
    do relatório. Os tempos são o menor ``completed_at`` de cada tarefa, ou
    None se não houve resultado. ``energy_used`` é None quando alguma
    autonomia é desconhecida. Com ``extra_initiators``, acrescenta as
    contagens de incidentes de todos os iniciadores.

    Args:
        report (dict[str, Any]): Relatório de uma execução de ``run_mvp``.

    Returns:
        dict[str, Any]: Métricas da execução (classificação, tempos em segundos simulados,
            energia em pontos percentuais, mensagens, missões e, com vários iniciadores,
            contagens de incidentes).
    """
    truth = any(event["is_threat"] for event in report["ground_truth"]["events"])
    decision = (report["decision"] or {}).get("decision")
    results = [result["payload"] for result in report["results"]]
    verify = [r["completed_at"] for r in results if r["task"] == "verify_incident"]
    respond = [r["completed_at"] for r in results if r["task"] == RANGER_TASK]
    initial = {r["resource_id"]: r["autonomy_percent"] for r in report["initial_resources"]}
    known_autonomy = (all(value is not None for value in initial.values())
                      and all(r["autonomy_percent"] is not None for r in report["resources"]))
    energy_used = (sum(initial[r["resource_id"]] - r["autonomy_percent"]
                       for r in report["resources"]) if known_autonomy else None)
    faults = [entry["fault"] for entry in report["fault_log"]]
    # Conhecimento do coordenador, não todas as conclusões da timeline móvel.
    statuses = [mission["status"] for mission in report["missions"]]
    # Vários iniciadores (Bloco F2, cenário D): as colunas acima são as do sensor-1; estas contam todos.
    extras = report.get("extra_initiators") or {}
    incidents = [view["incident_status"] for view in (report, *extras.values()) if view["incident_status"]]
    closed = [e["time"] for e in report["timeline"] if e["event"] == "INCIDENT_CLOSED" and e.get("status") == "closed"]
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
        "energy_used": energy_used,
        "messages_sent": len(report["messages"]),
        "messages_lost": faults.count("lost"),
        "messages_duplicated": faults.count("duplicated"),
        "missions_done": statuses.count("done"),
        "missions_failed": statuses.count("failed"),
        # Entradas de execução móvel trazem posição; as do sensor não.
        "first_patrol": next((e["resource_id"] for e in report["timeline"]
                              if e["event"] == "reserved" and "position" in e
                              and not e["resource_id"].startswith("ranger")), None),
        **({"incidents": len(incidents), "incidents_closed": incidents.count("closed"),
            "incidents_expired": incidents.count("expired"),
            "incidents_unresolved": incidents.count("unresolved"),
            # Subconjunto das fechadas: o iniciador desistiu porque um vizinho ficou com a ameaça.
            "incidents_duplicate": sum(view["reason"] == "duplicate_alert" for view in (report, *extras.values())),
            "last_close_time": max(closed, default=None)} if extras else {}),
    }


def describe(values):
    """Devolver n, média, mediana e desvio-padrão amostral, ignorando os None.

    Sem valores, as estatísticas são None com n = 0; com um só valor, o
    desvio-padrão é None.

    Args:
        values (Iterable[float | None]): Valores de uma métrica, um por execução.

    Returns:
        dict[str, float | int | None]: ``n``, ``mean``, ``median`` e ``stdev``.
    """
    values = [value for value in values if value is not None]
    if not values:
        return {"n": 0, "mean": None, "median": None, "stdev": None}
    return {"n": len(values), "mean": mean(values), "median": median(values),
            "stdev": stdev(values) if len(values) > 1 else None}


def summarize(rows):
    """Agregar as linhas de run_metrics de um mesmo cenário e variante.

    Com vários iniciadores, as métricas de classificação ficam a None e somam-se as
    contagens de incidentes.

    Args:
        rows (list[dict[str, Any]]): Resultados de ``run_metrics``, um por execução (repetição × episódio).

    Returns:
        dict[str, Any]: Número de execuções, classificação, contagens e estatísticas de
            ``describe`` para cada métrica numérica.

    Raises:
        ValueError: Se umas linhas tiverem contagens de incidentes e outras não.
    """
    multiple = ["incidents" in row for row in rows]
    if any(multiple) and not all(multiple):
        raise ValueError("Não é possível agregar unidades de avaliação diferentes.")
    if any(multiple):
        classification = dict.fromkeys(("TP", "FP", "TN", "FN", "precision", "recall", "fpr", "accuracy"))
    else:
        counts = confusion((row["threat"], row["dispatched"]) for row in rows)
        classification = {**counts, **rates(counts)}
    # D histórico não registava duplicados. Não inventar zero nem somar dados parciais.
    incident_fields = ("incidents", "incidents_closed", "incidents_expired", "incidents_unresolved")
    if rows and all("incidents_duplicate" in row for row in rows):
        incident_fields += ("incidents_duplicate",)
    return {"runs": len(rows), **classification,
            "confirmed_runs": sum(row["confirmed"] for row in rows),
            "unresolved_runs": sum(row["unresolved"] for row in rows),
            **{name: describe(row[name] for row in rows) for name in NUMERIC},
            **({name: sum(row[name] for row in rows)
                for name in incident_fields}
               if any(multiple) else {})}

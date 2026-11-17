"""Análise descritiva emparelhada dos lotes consolidados do Bloco G.

PYTHONPATH=src python scripts/analyze_sensitivity.py results/sensitivity/consolidado

Os intervalos de reamostragem descrevem a trajetória observada. A reputação
sequencial impede tratar as vinte sementes como clusters independentes; não
são intervalos inferenciais validados nem testes de significância.
"""

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
from statistics import mean

try:
    from scripts import consolidate_sensitivity as consolidation
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import consolidate_sensitivity as consolidation

from isia.evaluation.calibration import calibration_tables, initial_score
from isia.evaluation.metrics import NUMERIC, confusion, rates, run_metrics


sensitivity = consolidation.sensitivity
CLASSIFICATION = ("TP", "FP", "TN", "FN", "precision", "recall", "fpr", "accuracy")
EXTRA = ("confirmed_runs", "unresolved_runs", "expired_runs", "reason_insufficient_corroboration",
         "reason_no_eligible_proposals", "reason_confirmation_unknown", "reason_mission_result_unknown",
         "autonomy_insufficient", "ranger_missions_known", "ranger_cfp_sent", "reputation_updates",
         "reputation_sensor_1_final", "tempo_real_total_s", "tempo_real_medio_s")
INTERVAL_METRICS = ("precision", "recall", "fpr", "accuracy", "confirmed_rate", "unresolved_rate", *NUMERIC)
CHANGED_FIELDS = ("alert", "dispatched", "decision", "confirmed", "status", "reason", "verification_time",
                  "response_time", "energy_used", "messages_sent", "messages_lost", "messages_duplicated", "missions_done",
                  "missions_failed", "first_patrol", "reputation_sensor_1")
LIMITATIONS = [
    "Intervalos centrais de reamostragem descritiva; não demonstram significância estatística.",
    "A reputação aprende entre sementes: os vinte clusters não são independentes; a reamostragem não conserva essa dependência.",
    "Mesmas sementes não garantem as mesmas perdas em C: a ordem dos envios assíncronos depende das decisões.",
    "Tempos emparelhados usam apenas execuções com valor nos dois braços; a cobertura acompanha a diferença.",
    "A calibração é condicionada à existência de score; execuções sem score não recebem um zero artificial.",
    "As referências repetidas permanecem separadas por lote; não são novas amostras independentes.",
    "O tempo real total e médio depende da máquina e da carga durante a recolha; as diferenças são descritivas, sem bootstrap.",
]


def number(value):
    return None if value in (None, "N/A") else float(value)


def delta(before, after):
    absolute = None if before is None or after is None else after - before
    relative = None if absolute is None or before == 0 else absolute / before
    return absolute, relative


def identity(row):
    return tuple(str(row[name]) for name in ("repetition", "episode", "seed"))


def paired_rows(baseline, alternative):
    before = {identity(row): row for row in baseline}
    after = {identity(row): row for row in alternative}
    if len(before) != len(baseline) or len(after) != len(alternative) or before.keys() != after.keys():
        raise ValueError("As alternativas exigem os mesmos pares únicos de repetição/episódio/semente.")
    pairs = [(row, after[identity(row)]) for row in baseline]
    if any(first["threat"] != second["threat"] for first, second in pairs):
        raise ValueError("A verdade de referência deve coincidir em cada par.")
    return pairs


def group_metrics(rows):
    counts = confusion((row["threat"], row["dispatched"]) for row in rows)
    return {**counts, **rates(counts),
            "confirmed_rate": mean(row["confirmed"] for row in rows),
            "unresolved_rate": mean(row["unresolved"] for row in rows)}


def paired_values(pairs, metric):
    if metric in NUMERIC:
        available = [(before[metric], after[metric]) for before, after in pairs
                     if before[metric] is not None and after[metric] is not None]
        return ((mean(before for before, _ in available), mean(after for _, after in available), len(available))
                if available else (None, None, 0))
    before, after = (group_metrics([pair[side] for pair in pairs])[metric] for side in (0, 1))
    return before, after, len(pairs)


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    point = (len(ordered) - 1) * fraction
    lower = int(point)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (point - lower)


def descriptive_intervals(pairs, *, samples, seed):
    """Reamostrar sementes emparelhadas, mantendo juntos os episódios da semente."""
    if type(samples) is not int or samples < 1 or type(seed) is not int:
        raise ValueError("O bootstrap exige amostras positivas e uma semente inteira.")
    clusters = defaultdict(list)
    for pair in pairs:
        clusters[str(pair[0]["seed"])].append(pair)
    blocks = list(clusters.values())
    if not blocks:
        raise ValueError("Não existem pares para reamostrar.")
    rng = random.Random(seed)
    differences = {metric: [] for metric in INTERVAL_METRICS}
    for _ in range(samples):
        selected = [pair for _ in blocks for pair in rng.choice(blocks)]
        first, second = ([pair[side] for pair in selected] for side in (0, 1))
        before, after = group_metrics(first), group_metrics(second)
        for metric in INTERVAL_METRICS:
            left, right, _ = (paired_values(selected, metric) if metric in NUMERIC
                              else (before[metric], after[metric], len(selected)))
            if left is not None and right is not None:
                differences[metric].append(right - left)
    return {metric: {"descriptive_delta_p025": percentile(values, 0.025),
                     "descriptive_delta_p975": percentile(values, 0.975),
                     "bootstrap_valid_samples": len(values), "bootstrap_samples": samples,
                     "bootstrap_seed": seed, "n_seed_clusters": len(blocks),
                     "interval_method": "descriptive_paired_seed_cluster_bootstrap",
                     "interval_target": "paired_delta",
                     "inferential_interval": False}
            for metric, values in differences.items()}


def compare_group(baseline, alternative, before_summary, after_summary, *, samples=2000, seed=917):
    pairs = paired_rows(baseline, alternative)
    metadata = {name: after_summary[name] for name in ("batch_id", "parametro", "valor", "cenario")}
    intervals = descriptive_intervals(pairs, samples=samples, seed=seed)
    summary = {**metadata, "n_runs": len(pairs), "n_seeds": len({row["seed"] for row in baseline}),
               "changed_classification_runs": sum(first["dispatched"] != second["dispatched"] for first, second in pairs),
               "changed_metric_runs": sum(any(first.get(field) != second.get(field) for field in CHANGED_FIELDS)
                                          for first, second in pairs),
               "baseline_first_patrol_counts": sensitivity.encoded(dict(Counter(row.get("first_patrol") or "N/A" for row in baseline))),
               "alternative_first_patrol_counts": sensitivity.encoded(dict(Counter(row.get("first_patrol") or "N/A" for row in alternative)))}
    effects = []
    before_rates, after_rates = group_metrics(baseline), group_metrics(alternative)
    metrics = [*CLASSIFICATION, "confirmed_rate", "unresolved_rate",
               *(f"{name}_mean" for name in NUMERIC), *EXTRA]
    for metric in metrics:
        if metric in ("confirmed_rate", "unresolved_rate"):
            left, right = before_rates[metric], after_rates[metric]
        else:
            left, right = number(before_summary.get(metric)), number(after_summary.get(metric))
        absolute, relative = delta(left, right)
        summary.update({f"baseline_{metric}": left, f"alternative_{metric}": right,
                        f"delta_{metric}": absolute, f"relative_{metric}": relative})
        paired_metric = metric.removesuffix("_mean") if metric.endswith("_mean") else metric
        effect = {**metadata, "metric": metric,
                  "category": "classification" if metric in CLASSIFICATION else "operational",
                  "baseline": left, "alternative": right, "delta_absolute": absolute,
                  "delta_relative": relative}
        if metric in ("precision", "recall", "fpr", "accuracy"):
            def denominator(values):
                if metric == "precision":
                    return values["TP"] + values["FP"]
                if metric == "recall":
                    return values["TP"] + values["FN"]
                if metric == "fpr":
                    return values["FP"] + values["TN"]
                return sum(values[name] for name in ("TP", "FP", "TN", "FN"))
            effect.update(baseline_denominator=denominator(before_rates),
                          alternative_denominator=denominator(after_rates))
        if paired_metric in INTERVAL_METRICS:
            paired_before, paired_after, n_pairs = paired_values(pairs, paired_metric)
            paired_delta, paired_relative = delta(paired_before, paired_after)
            baseline_n = sum(row[paired_metric] is not None for row in baseline) if paired_metric in NUMERIC else len(baseline)
            alternative_n = sum(row[paired_metric] is not None for row in alternative) if paired_metric in NUMERIC else len(alternative)
            effect.update(baseline_n=baseline_n, alternative_n=alternative_n, paired_n=n_pairs,
                          coverage_delta=(alternative_n - baseline_n) / len(pairs),
                          baseline_paired=paired_before, alternative_paired=paired_after,
                          paired_delta=paired_delta, paired_relative_delta=paired_relative,
                          **intervals[paired_metric])
            summary.update({f"paired_delta_{paired_metric}": paired_delta,
                            f"paired_n_{paired_metric}": n_pairs,
                            f"coverage_delta_{paired_metric}": effect["coverage_delta"]})
        effects.append(effect)
    return summary, effects


def load_consolidated(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("mode") != "consolidation" or manifest.get("status") != "complete":
        raise ValueError("A análise exige uma consolidação concluída.")
    for source in manifest["sources"]:
        for name, digest in source["sha256"].items():
            if consolidation._hash(Path(source["path"]) / name) != digest:
                raise ValueError("Um lote original foi alterado depois da consolidação.")
    batches, provenance, alternatives = consolidation.load_batches([source["path"] for source in manifest["sources"]])
    runs = sensitivity.read_csv(directory / "runs.csv")
    summaries = sensitivity.read_csv(directory / "summary.csv")
    expected_runs = [{"batch_id": batch["batch_id"], **row} for batch in batches for row in batch["runs"]]
    expected_summary = [{"batch_id": batch["batch_id"], **row} for batch in batches for row in batch["summaries"]]
    if runs != expected_runs or summaries != expected_summary:
        raise ValueError("Os CSV consolidados não correspondem aos lotes originais.")
    if manifest.get("alternative_groups") != len(alternatives) or manifest.get("runs") != len(runs):
        raise ValueError("As contagens da consolidação estão incoerentes.")
    typed = []
    for row in runs:
        converted = consolidation._typed(row)
        converted["reputation_sensor_1"] = number(row["reputation_sensor_1"])
        typed.append(converted)
    return manifest, typed, summaries


def report_application(report, parameter, value):
    """Verificar configurações efetivas disponíveis no relatório operacional."""
    settings = report["response_settings"]
    if parameter == "corroboration_distance":
        actual = report["corroboration_settings"]["max_distance"]
    elif parameter == "corroboration_window":
        actual = report["corroboration_settings"]["max_time_difference"]
    elif parameter == "receive_timeout":
        actual = report["receive_timeout"]
    elif parameter == "minimum_autonomy":
        actual = report["minimum_autonomy_percent"]
    elif parameter == "cost_weights":
        actual = [report["selection_weights"][name] for name in ("eta_weight", "energy_weight", "load_weight")]
    elif parameter == "reputation_prior":
        actual = [settings["reputation"][name] for name in ("alpha", "beta")]
        value = [value, value]
    elif parameter in ("patrol_threshold", "ranger_threshold"):
        actual = settings["policy"][parameter]
    elif parameter == "source_diversity":
        actual = [settings["policy"][name] for name in ("ranger_min_groups", "ranger_min_modalities")]
        value = [value, value]
    elif parameter == "severity":
        actual = settings["severity"]
    elif parameter.startswith("adjudication_"):
        actual = settings["adjudication"]["max_distance" if parameter.endswith("distance") else "max_delay_seconds"]
    elif parameter == "sensor_quality":
        # Source não é serializado no relatório. A aplicação é verificada na
        # configuração efetiva do lote e na proveniência do runner, sem inventar telemetria.
        return "configuration_and_code_provenance", None
    else:
        raise ValueError(f"Fator desconhecido na auditoria: {parameter}.")
    if not sensitivity.alternative_matches(actual, value):
        raise ValueError(f"O relatório não confirma o override {parameter}={value!r}: {actual!r}.")
    return "effective_report_setting", actual


def verify_report(record, expected):
    metadata, report = record["metrics"], record["report"]
    expected_id = f"{metadata['scenario']}-full-{int(metadata['repetition']):03d}-{metadata['episode']}"
    if report["run_id"] != expected_id or report["scenario_seed"] != int(metadata["seed"]):
        raise ValueError("Identidade ou semente divergente entre relatório e métricas.")
    if sensitivity.compare_rows([metadata], [expected], identity=("scenario", "repetition", "episode", "seed")):
        raise ValueError("O relatório individual não corresponde à linha CSV.")
    if sensitivity.compare_rows([metadata], [run_metrics(report)], identity=()):
        raise ValueError("As métricas do envelope não correspondem ao relatório operacional.")


def calibration_and_audit(manifest, reference_reports):
    records, sources, application = [], [], defaultdict(list)
    expected = sensitivity.read_csv(sensitivity.REFERENCE_ROOT / "runs.csv")
    expected = [row for row in expected if row["variant"] == "full"]
    reference_records = []
    for path in sorted(Path(reference_reports).rglob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        metadata = record.get("metrics", {})
        if metadata.get("variant") == "full" and metadata.get("scenario") in ("A", "B", "C"):
            reference_records.append(record)
            sources.append({"path": str(path.resolve()), "sha256": consolidation._hash(path), "kind": "reference"})
    if len(reference_records) != 140 or sensitivity.compare_rows(
            [record["metrics"] for record in reference_records], expected,
            identity=("scenario", "variant", "repetition", "episode", "seed")):
        raise ValueError("A calibração de referência exige os 140 relatórios full correspondentes à Etapa 9.")
    expected_reference = {(row["scenario"], identity(row)): row for row in expected}
    for record in reference_records:
        expected_row = expected_reference[record["metrics"]["scenario"], identity(record["metrics"])]
        verify_report(record, expected_row)
        record = deepcopy(record)
        record["metrics"].update(parametro="baseline", valor=sensitivity.encoded("original"))
        records.append(record)
    for source in manifest["sources"]:
        source_manifest = json.loads((Path(source["path"]) / "manifest.json").read_text())
        expected_source = {(row["parametro"], row["valor"], row["scenario"], identity(row)): row
                           for row in sensitivity.read_csv(Path(source["path"]) / "runs.csv")}
        planned = {(item["parametro"], sensitivity.encoded(item["valor"]), item["cenario"]): item
                   for item in source_manifest["plan"] if item["status"] == "ready"}
        counts = Counter()
        for path in sorted(Path(source["reports_path"]).rglob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            metadata = record.get("metrics", {})
            if metadata.get("parametro") == "baseline":
                continue
            key = metadata["parametro"], metadata["valor"], metadata["scenario"]
            if key not in planned:
                raise ValueError("Um relatório individual não corresponde ao plano do lote.")
            item = planned[key]
            verify_report(record, expected_source[(*key, identity(metadata))])
            method, actual = report_application(record["report"], item["parametro"], item["valor"])
            application[key].append((method, actual))
            counts[key] += 1
            records.append(record)
            sources.append({"path": str(path.resolve()), "sha256": consolidation._hash(path), "kind": "alternative"})
        if counts != Counter({key: item["runs"] for key, item in planned.items()}):
            raise ValueError("Faltam relatórios individuais das alternativas.")
    bins, coverage = calibration_tables(records)
    samples = [{**{name: record["metrics"][name] for name in ("scenario", "parametro", "valor")},
                "repetition": record["metrics"]["repetition"], "episode": record["metrics"]["episode"],
                "seed": record["metrics"]["seed"], "score": initial_score(record["report"]),
                "threat": any(event["is_threat"] for event in record["report"]["ground_truth"]["events"])}
               for record in records]
    audit = [{"parametro": key[0], "valor": key[1], "cenario": key[2], "n_reports": len(values),
              "application_method": values[0][0], "reported_values": sensitivity.encoded([value for _, value in values[:1]]),
              "configuration_verified": True,
              "runtime_setting_reported": values[0][0] == "effective_report_setting"}
             for key, values in sorted(application.items())]
    return bins, coverage, samples, audit, sources


def analyze(directory, *, reference_reports=None, run_id=None, bootstrap_samples=2000, bootstrap_seed=917):
    manifest, runs, summaries = load_consolidated(directory)
    grouped = defaultdict(list)
    for row in runs:
        grouped[(row["batch_id"], *consolidation._group(row))].append(row)
    indexed = {(row["batch_id"], *consolidation._group(row)): row for row in summaries}
    comparisons, effects = [], []
    for key, rows in grouped.items():
        batch, parameter, value, scenario = key
        if parameter == "baseline":
            continue
        baseline_key = batch, "baseline", sensitivity.encoded("original"), scenario
        comparison, rows_effects = compare_group(grouped[baseline_key], rows, indexed[baseline_key], indexed[key],
                                                 samples=bootstrap_samples, seed=bootstrap_seed)
        comparisons.append(comparison)
        effects.extend(rows_effects)
    bins, coverage, samples, audit, sources = calibration_and_audit(
        manifest, reference_reports or sensitivity.REFERENCE_ROOT / "runs")
    output = sensitivity.create_output(run_id)
    result = {"mode": "analysis", "status": "running", "source": str(Path(directory).resolve()),
              "source_hashes": {name: consolidation._hash(Path(directory) / name)
                                for name in ("manifest.json", "runs.csv", "summary.csv")},
              "analysis_sha256": consolidation._hash(Path(__file__)), "bootstrap_samples": bootstrap_samples,
              "bootstrap_seed": bootstrap_seed, "bootstrap_inferential": False,
              "relative_delta_definition": "(alternative-baseline)/baseline; N/A if baseline zero or undefined",
              "selection_complete": manifest["selection_complete"], "limitations": LIMITATIONS,
              "calibration_inputs": sources, "total_simulations": 0}
    try:
        for name, rows in (("comparisons.csv", comparisons), ("effects.csv", effects),
                           ("calibration.csv", bins), ("calibration-coverage.csv", coverage),
                           ("calibration-samples.csv", samples), ("application-audit.csv", audit)):
            sensitivity.write_csv(output / name, rows)
        findings = {"groups": len(comparisons), "alternative_runs": sum(row["n_runs"] for row in comparisons),
                    "no_classification_difference": [row for row in comparisons if row["changed_classification_runs"] == 0],
                    "no_recorded_metric_difference": [row for row in comparisons if row["changed_metric_runs"] == 0],
                    "largest_classification_changes": sorted(comparisons,
                        key=lambda row: max(abs(row[f"delta_{metric}"] or 0) for metric in ("recall", "fpr", "precision")), reverse=True),
                    "limitations": LIMITATIONS}
        sensitivity.write_json(output / "findings.json", findings)
        result.update(status="complete", groups=len(comparisons), alternative_runs=findings["alternative_runs"])
    except Exception as error:
        result.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        sensitivity.write_json(output / "manifest.json", result)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("consolidation", type=Path)
    parser.add_argument("--reference-reports", type=Path, default=sensitivity.REFERENCE_ROOT / "runs")
    parser.add_argument("--run-id")
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=917)
    args = parser.parse_args(argv)
    try:
        output = analyze(args.consolidation, reference_reports=args.reference_reports, run_id=args.run_id,
                         bootstrap_samples=args.bootstrap_samples, bootstrap_seed=args.bootstrap_seed)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(f"Análise sem simulações: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

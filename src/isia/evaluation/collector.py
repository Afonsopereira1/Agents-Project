"""Executar cenários × variantes × sementes e guardar relatórios e métricas (Etapa 9).

python -m isia.evaluation.collector config/scenarios/*.json --output results/experiments
"""

import argparse
import asyncio
import csv
import json
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path

from isia.evaluation.metrics import NUMERIC, run_metrics, summarize
from isia.reasoning.reputation import ReputationBook
from isia.simulation.runner import run_mvp


# Cada ablação muda uma só coisa face a "full".
VARIANTS = {
    "full": {},
    # Prior fixo em todas as execuções: sem aprendizagem entre elas.
    "no_reputation": {"learn": False},
    # Ignora o par e mobiliza com qualquer score positivo de uma só fonte.
    "no_corroboration": {"corroborate": False,
                         "policy": {"patrol_threshold": 0.01, "severe_patrol_threshold": 0.01}},
    # Só ETA: com velocidades iguais é a patrulha elegível mais próxima.
    "nearest": {"selection_weights": {"energy_weight": 0.0, "load_weight": 0.0}},
}


def load_scenario(path):
    with open(path, encoding="utf-8") as stream:
        config = json.load(stream)
    expected = {"scenario_id", "description", "repetitions", "base_seed", "episodes",
                "sources", "resources", "faults", "response_settings"}
    if set(config) != expected:
        raise ValueError(f"{path}: o cenário exige {sorted(expected)}.")
    if type(config["repetitions"]) is not int or config["repetitions"] < 1:
        raise ValueError(f"{path}: repetitions deve ser inteiro positivo.")
    if not isinstance(config["episodes"], list) or not config["episodes"] or any(
            not isinstance(e, dict) or set(e) != {"label", "events"} for e in config["episodes"]):
        raise ValueError(f"{path}: episodes deve ser uma lista não vazia de {{label, events}}.")
    return config


async def run_scenario(config, variant, *, repetitions=None, output=None):
    """Execuções sequenciais; em "full" a reputação aprende ao longo delas."""
    options = VARIANTS[variant]
    settings = deepcopy(config["response_settings"])
    settings["policy"].update(options.get("policy", {}))
    book = ReputationBook(**settings["reputation"])
    rows = []
    for repetition in range(repetitions or config["repetitions"]):
        seed = config["base_seed"] + repetition
        for episode in config["episodes"]:
            run_id = f"{config['scenario_id']}-{variant}-{repetition:03d}-{episode['label']}"
            if not options.get("learn", True):
                book = ReputationBook(**settings["reputation"])
            faults = None if config["faults"] is None else {**config["faults"], "seed": seed}
            report = await run_mvp(
                response_settings=settings, reputation=book, faults=faults,
                scenario={"run_id": run_id, "seed": seed, "sources": config["sources"],
                          "events": episode["events"], "resources": config["resources"]},
                corroborate=options.get("corroborate", True),
                selection_weights=options.get("selection_weights"), max_seconds=30.0)
            row = {"scenario": config["scenario_id"], "variant": variant, "repetition": repetition,
                   "episode": episode["label"], "seed": seed, **run_metrics(report),
                   "reputation_sensor_1": book.score("sensor-1")}
            rows.append(row)
            if output is not None:
                path = Path(output) / config["scenario_id"] / variant / f"{run_id}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"metrics": row, "report": report},
                                           ensure_ascii=False, indent=1, default=str) + "\n")
    return rows


def flat_summary(scenario, variant, rows):
    summary = summarize(rows)
    flat = {"scenario": scenario, "variant": variant}
    for key, value in summary.items():
        if key in NUMERIC:
            for stat in ("mean", "median", "stdev", "n"):
                flat[f"{key}_{stat}"] = value[stat]
        else:
            flat[key] = value
    return flat


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows([{k: "N/A" if v is None else v for k, v in row.items()} for row in rows])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenarios", nargs="+", type=Path)
    parser.add_argument("--variants", nargs="+", choices=sorted(VARIANTS), default=list(VARIANTS))
    parser.add_argument("--repetitions", type=int, help="Substitui repetitions dos cenários")
    parser.add_argument("--output", type=Path, default=Path("results/experiments"))
    args = parser.parse_args()
    if args.repetitions is not None and args.repetitions < 1:
        parser.error("--repetitions deve ser positivo.")
    try:
        configs = [load_scenario(path) for path in args.scenarios]
    except (OSError, ValueError) as error:
        parser.error(str(error))
    # Proveniência lida antes de correr: commits ou edições durante a recolha não contam.
    git = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True).stdout.strip()
    commit = git("rev-parse", "HEAD") or None
    dirty = bool(git("status", "--porcelain", "--", "src", "config"))
    # Tudo o que é desta recolha sai junto; se ela falhar, fica sem manifesto (incompleta).
    shutil.rmtree(args.output / "runs", ignore_errors=True)
    for name in ("runs.csv", "summary.csv", "manifest.json"):
        (args.output / name).unlink(missing_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)

    async def collect():
        runs, summaries = [], []
        for config in configs:
            for variant in args.variants:
                rows = await run_scenario(config, variant, repetitions=args.repetitions,
                                          output=args.output / "runs")
                runs.extend(rows)
                summaries.append(flat_summary(config["scenario_id"], variant, rows))
                print(json.dumps(summaries[-1], ensure_ascii=False))
        return runs, summaries

    runs, summaries = asyncio.run(collect())
    write_csv(args.output / "runs.csv", runs)
    write_csv(args.output / "summary.csv", summaries)
    (args.output / "manifest.json").write_text(json.dumps({
        # dirty: alterações sem commit em código ou cenários tornam o commit insuficiente.
        "commit": commit, "dirty": dirty,
        "scenarios": [str(p) for p in args.scenarios],
        "variants": {name: VARIANTS[name] for name in args.variants},
        "repetitions_override": args.repetitions, "runs": len(runs),
    }, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()

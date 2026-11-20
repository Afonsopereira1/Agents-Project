"""Consolidar lotes completos do Bloco G, sem simular nem combinar trajetórias.

PYTHONPATH=src python scripts/consolidate_sensitivity.py results/sensitivity/lote1 results/sensitivity/lote2
"""

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path

try:
    from scripts import sensitivity
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import sensitivity

from isia.evaluation.metrics import NUMERIC


def _hash(path):
    """Calcular o SHA-256 (hexadecimal) do conteúdo do ficheiro."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _key(parameter, value, scenario):
    """Devolver a chave canónica (parâmetro, valor em JSON, cenário) de uma alternativa."""
    # JSON 2 e 2.0 identificam a mesma alternativa; bool nunca equivale a 1.
    for candidate in sensitivity.PARAMETERS.get(parameter, {}).get("alternatives", ()):
        if sensitivity.alternative_matches(value, candidate):
            value = candidate
            break
    return parameter, sensitivity.encoded(value), scenario


def _group(row):
    """Devolver a chave de grupo de uma linha CSV; recusa etiquetas incoerentes.

    Raises:
        ValueError: Se ``cenario`` e ``scenario`` diferirem ou a variante não for ``full``.
    """
    if row["cenario"] != row["scenario"] or row["variant"] != "full":
        raise ValueError("As etiquetas de cenário/variante do CSV são incoerentes.")
    return _key(row["parametro"], json.loads(row["valor"]), row["cenario"])


def _typed(row):
    """Copiar uma linha CSV com booleanos e métricas numéricas convertidos.

    "N/A" passa a ``None``.

    Raises:
        ValueError: Para booleanos diferentes de "True"/"False" e para números negativos ou
            não finitos.
    """
    result = dict(row)
    for field in ("threat", "alert", "dispatched", "confirmed", "unresolved"):
        if row[field] not in ("True", "False"):
            raise ValueError(f"{field} deve ser booleano no CSV.")
        result[field] = row[field] == "True"
    for field in NUMERIC:
        value = None if row[field] == "N/A" else float(row[field])
        if value is not None and (not math.isfinite(value) or value < 0):
            raise ValueError(f"{field} deve ser finito e não negativo ou N/A.")
        result[field] = value
    return result


def load_batches(paths):
    """Validar lotes inteiros antes de criar qualquer pasta de saída.

    As referências ficam separadas por lote. Repetições reduzidas e alternativas
    sobrepostas são recusadas, evitando tratar replays como amostras novas.

    Args:
        paths (list[str | Path]): Pastas dos lotes, todas diretamente em ``results/sensitivity/``.

    Returns:
        tuple[list[dict], dict, set[tuple[str, str, str]]]: Os lotes (``batch_id``, ``path``,
            ``sha256``, ``reports_path``, ``runs``, ``summaries``), a proveniência comum e as
            chaves (parâmetro, valor em JSON, cenário) das alternativas concluídas.

    Raises:
        ValueError: Se houver menos de dois lotes, pastas repetidas ou fora do sítio, ou se
            algum lote estiver incompleto, tiver proveniência incompatível, repetições
            diferentes de 20, alternativas sobrepostas ou CSV incoerentes com o plano.
    """
    if len(paths) < 2:
        raise ValueError("A consolidação exige pelo menos duas pastas de lotes.")
    directories = [Path(path).resolve() for path in paths]
    root = sensitivity.OUTPUT_ROOT.resolve()
    if len(set(directories)) != len(directories) or any(path.parent != root for path in directories):
        raise ValueError("Selecionar pastas distintas diretamente em results/sensitivity/.")
    common, alternatives, batches = None, set(), []
    required_runs = set(sensitivity.read_csv(sensitivity.REFERENCE_ROOT / "runs.csv")[0])
    required_summary = set(sensitivity.read_csv(sensitivity.REFERENCE_ROOT / "summary.csv")[0])
    for directory in directories:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if (manifest.get("status") not in ("complete", "complete_with_blocked")
                or manifest.get("mode", "collection") != "collection"
                or manifest.get("variant") != "full"
                or manifest.get("extensions_bloco_f") != "disabled"
                or manifest.get("self_check", {}).get("passed") is not True):
            raise ValueError(f"{directory.name}: lote não concluído ou referência não aprovada.")
        provenance = manifest["provenance"]
        signature = {key: provenance[key] for key in
                     ("commit", "sha256", "reference_sha256", "python", "spade", "platform")}
        required_code = {"scripts/sensitivity.py", "src/isia/evaluation/collector.py",
                         "src/isia/simulation/runner.py", "requirements.txt",
                         *(f"config/scenarios/{name}.json" for name in ("A", "B", "C"))}
        if (not required_code <= set(signature["sha256"])
                or not {"runs.csv", "summary.csv", "manifest.json"} <= set(signature["reference_sha256"])):
            raise ValueError("A proveniência deve incluir hashes do código e das referências.")
        if common is not None and signature != common:
            raise ValueError("Os lotes têm proveniência incompatível.")
        common = signature
        configs = {config["scenario_id"]: config for config in manifest["scenarios"]}
        if not configs or len(configs) != len(manifest["scenarios"]):
            raise ValueError("Cada lote deve identificar cenários únicos.")
        override = manifest.get("repetitions_override")
        if override is not None and (type(override) is not int or override != 20):
            raise ValueError("A consolidação final exige as 20 repetições; pilotos são recusados.")
        expected = {}
        for name, config in configs.items():
            if name not in ("A", "B", "C") or config != sensitivity.load_scenario(
                    sensitivity.SCENARIO_ROOT / f"{name}.json"):
                raise ValueError("Os cenários do lote devem coincidir com os JSON oficiais.")
            expected[("baseline", sensitivity.encoded("original"), name)] = config
        ready = [item for item in manifest["plan"] if item["status"] == "ready"]
        if not ready or any(item["status"] not in ("ready", "blocked") for item in manifest["plan"]):
            raise ValueError("O lote não contém alternativas válidas concluídas.")
        local_alternatives = set()
        for item in ready:
            key = _key(item["parametro"], item["valor"], item["cenario"])
            if key in alternatives or key in local_alternatives:
                raise ValueError(f"Alternativa sobreposta entre lotes: {key}.")
            original = configs[item["cenario"]]
            configured, options = sensitivity.apply_experiment(original, item["parametro"], item["valor"])
            if configured != item["config"] or options != item["runner_options"]:
                raise ValueError("O override registado não corresponde ao fator experimental.")
            if (item["repetitions"] != 20 or item["seeds"] != list(range(original["base_seed"], original["base_seed"] + 20))
                    or item["episodes"] != [episode["label"] for episode in original["episodes"]]):
                raise ValueError("As sementes, episódios ou repetições do lote divergem da referência.")
            local_alternatives.add(key)
            expected[key] = configured
        runs = sensitivity.read_csv(directory / "runs.csv")
        summaries = sensitivity.read_csv(directory / "summary.csv")
        if (not runs or not summaries or not required_runs <= set(runs[0])
                or not required_summary <= set(summaries[0])
                or any("batch_id" in row for row in runs + summaries)):
            raise ValueError("CSV vazio, sem colunas obrigatórias ou já consolidado.")
        grouped = defaultdict(list)
        summary_groups = {}
        for row in runs:
            grouped[_group(row)].append(row)
        for row in summaries:
            key = _group(row)
            if key in summary_groups:
                raise ValueError("Resumo duplicado no mesmo lote.")
            summary_groups[key] = row
        if set(grouped) != set(expected) or set(summary_groups) != set(expected):
            raise ValueError("Os grupos CSV não correspondem ao plano completo do lote.")
        for key, config in expected.items():
            rows, summary = grouped[key], summary_groups[key]
            planned = [(str(rep), episode["label"], str(config["base_seed"] + rep))
                       for rep in range(20) for episode in config["episodes"]]
            if [(row["repetition"], row["episode"], row["seed"]) for row in rows] != planned:
                raise ValueError("Execuções incompletas, duplicadas ou fora da ordem original.")
            aggregate = sensitivity.flat_summary(key[2], "full", [_typed(row) for row in rows])
            if sensitivity.compare_rows([summary], [aggregate], identity=("scenario", "variant")):
                raise ValueError("O resumo não corresponde às execuções individuais.")
            if (summary["repetitions"] != "20"
                    or json.loads(summary["seeds"]) != list(range(config["base_seed"], config["base_seed"] + 20))
                    or json.loads(summary["episodes"]) != [episode["label"] for episode in config["episodes"]]):
                raise ValueError("A cobertura declarada no resumo é incoerente.")
        if manifest["runs"] != len(runs):
            raise ValueError("A contagem do manifesto não corresponde ao CSV.")
        alternatives.update(local_alternatives)
        batches.append({"batch_id": directory.name, "path": str(directory),
                        "sha256": {name: _hash(directory / name) for name in ("manifest.json", "runs.csv", "summary.csv")},
                        "reports_path": str(directory / "runs"), "runs": runs, "summaries": summaries})
    return batches, common, alternatives


def consolidate(paths, run_id=None):
    """Juntar ``runs.csv`` e ``summary.csv`` dos lotes validados numa pasta nova.

    Cada linha recebe o ``batch_id`` de origem; o manifesto regista os grupos em falta e,
    depois de criada a pasta, é gravado mesmo que a escrita falhe (lotes inválidos falham
    antes de criar qualquer pasta).

    Args:
        paths (list[str | Path]): Pastas dos lotes a juntar (ver ``load_batches``).
        run_id (str | None): Nome da pasta nova em ``results/sensitivity/``; ``None`` gera um.

    Returns:
        Path: A pasta de saída, com ``runs.csv``, ``summary.csv`` e ``manifest.json``.
    """
    batches, provenance, alternatives = load_batches(paths)
    expected = {(parameter, sensitivity.encoded(value), scenario)
                for parameter, spec in sensitivity.PARAMETERS.items() for value in spec["alternatives"]
                if not (parameter == "source_diversity" and value == 1) for scenario in ("A", "B", "C")}
    output = sensitivity.create_output(run_id)
    manifest = {"mode": "consolidation", "status": "running", "provenance": provenance,
                "consolidator_sha256": _hash(Path(__file__)),
                "selection_complete": not expected - alternatives,
                "missing_groups": [dict(zip(("parametro", "valor", "cenario"), group))
                                   for group in sorted(expected - alternatives)],
                "baseline_policy": "separate_by_batch_id; never pooled",
                "sources": [{key: value for key, value in batch.items() if key not in ("runs", "summaries")}
                            for batch in batches]}
    try:
        runs = [{"batch_id": batch["batch_id"], **row} for batch in batches for row in batch["runs"]]
        summaries = [{"batch_id": batch["batch_id"], **row} for batch in batches for row in batch["summaries"]]
        sensitivity.write_csv(output / "runs.csv", runs)
        sensitivity.write_csv(output / "summary.csv", summaries)
        manifest.update(status="complete", runs=len(runs), groups=len(summaries),
                        alternative_groups=len(alternatives), total_simulations=0)
    except Exception as error:
        manifest.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        sensitivity.write_json(output / "manifest.json", manifest)
    return output


def main(argv=None):
    """Ler os argumentos e consolidar os lotes; erros de dados terminam via ``parser.error``.

    Args:
        argv (list[str] | None): Argumentos da linha de comandos; ``None`` usa ``sys.argv``.

    Returns:
        int: 0 quando a consolidação termina.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batches", nargs="+", type=Path)
    parser.add_argument("--run-id", help="Nova pasta exclusiva em results/sensitivity/")
    args = parser.parse_args(argv)
    try:
        output = consolidate(args.batches, args.run_id)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(f"Consolidação sem simulações: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

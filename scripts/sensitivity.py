"""Bloco G: experiências de um fator, sem alterar os resultados da Etapa 9.

PYTHONPATH=src python scripts/sensitivity.py --parameter corroboration_distance --value 1 --scenario A --repetitions 1
"""

import argparse
import asyncio
import csv
import hashlib
import importlib.metadata
import json
import math
import platform
import re
import subprocess
import sys
import time
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from isia.evaluation.collector import (
    flat_summary, load_scenario, run_scenario, validate_runner_options, validate_scenario,
)
from isia.reasoning.policy import ResponsePolicy
from isia.reasoning.reputation import ReputationBook
from isia.simulation.runner import scenario_settings


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "results/sensitivity"
REFERENCE_ROOT = ROOT / "results/experiments"
SCENARIO_ROOT = ROOT / "config/scenarios"
# Cada tuplo é um fator experimental. Os fatores compostos estão definidos no plano:
# FP/FN, α=β, vetor de pesos, grupos/modalidades. Não se combinam fatores diferentes.
PARAMETERS = {
    "corroboration_distance": {"current": 3.0, "alternatives": (1.0, 5.0)},
    "corroboration_window": {"current": 2.0, "alternatives": (0.5, 5.0)},
    "sensor_quality": {"current": "scenario", "alternatives": ("ideal", "noisy")},
    "receive_timeout": {"current": 0.5, "alternatives": (0.1, 2.0)},
    "cost_weights": {"current": [1, 1, 1], "alternatives": ([0, 1, 0], [1, 1, 5])},
    "minimum_autonomy": {"current": 10.0, "alternatives": (5.0, 30.0)},
    "reputation_prior": {"current": 2.0, "alternatives": (0.5, 10.0)},
    "patrol_threshold": {"current": 0.25, "alternatives": (0.15, 0.35)},
    "ranger_threshold": {"current": 0.65, "alternatives": (0.5, 0.8)},
    "source_diversity": {"current": 2, "alternatives": (1, 3)},
    "severity": {"current": 0.5, "alternatives": (0.2, 0.9)},
    "adjudication_distance": {"current": 1, "alternatives": (0, 2)},
    "adjudication_delay": {"current": 30.0, "alternatives": (5.0, 120.0)},
}
BLOCKED_DIVERSITY = (
    "A alternativa 1 grupo / 1 modalidade viola ResponsePolicy (mínimo 2). "
    "Exige aprovação explícita de uma política experimental que relaxe a "
    "independência das fontes; a política de produção permanece inalterada."
)
UNSET = object()


class BlockedExperiment(ValueError):
    """Uma alternativa prevista exige alteração de contrato ainda não aprovada."""


def encoded(value):
    """Serializar em JSON canónico: chaves ordenadas, sem espaços, Unicode literal.

    Args:
        value (object): Valor serializável em JSON.

    Returns:
        str: Texto JSON, estável entre execuções (serve de chave e de coluna ``valor``).
    """
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def alternative_matches(value, candidate):
    """Dizer se um valor alternativo corresponde ao pedido.

    Números comparam-se por valor (2 e 2.0 equivalem; NaN e infinitos nunca); listas, elemento
    a elemento. JSON booleano/null nunca equivale a um número.

    Args:
        value (object): Valor pedido ou lido (ex.: de ``--value`` ou de um relatório).
        candidate (object): Alternativa prevista em ``PARAMETERS``.

    Returns:
        bool: ``True`` se os dois representarem a mesma alternativa.
    """
    if type(value) in (int, float) and type(candidate) in (int, float):
        return math.isfinite(value) and value == candidate
    if isinstance(value, list) and isinstance(candidate, list):
        return len(value) == len(candidate) and all(
            alternative_matches(left, right) for left, right in zip(value, candidate))
    return type(value) is type(candidate) and value == candidate


def apply_experiment(config, parameter, value):
    """Devolver cópias independentes (cenário, opções do runner) de um só fator.

    Args:
        config (dict): Cenário original, que não é alterado.
        parameter (str): Fator experimental (chave de ``PARAMETERS``).
        value (object): Alternativa a aplicar; tem de ser uma das previstas.

    Returns:
        tuple[dict, dict]: O cenário com o fator aplicado e as opções extra do runner.

    Raises:
        ValueError: Se o parâmetro for desconhecido, a alternativa não estiver prevista ou a
            configuração resultante for inválida (ver ``validate_configuration``).
        BlockedExperiment: Para ``source_diversity=1``, que exige aprovação explícita.
    """
    if parameter not in PARAMETERS:
        raise ValueError(f"Parâmetro desconhecido: {parameter}.")
    spec = PARAMETERS[parameter]
    if not any(alternative_matches(value, candidate) for candidate in spec["alternatives"]):
        raise ValueError(f"{parameter}: alternativa inválida {value!r}.")
    if parameter == "source_diversity" and value == 1:
        raise BlockedExperiment(BLOCKED_DIVERSITY)
    result, options = deepcopy(config), {}
    settings = result["response_settings"]
    if parameter in ("corroboration_distance", "corroboration_window"):
        key = "max_distance" if parameter.endswith("distance") else "max_time_difference"
        options["corroboration_settings"] = {key: value}
    elif parameter == "receive_timeout":
        options["receive_timeout"] = value
    elif parameter == "minimum_autonomy":
        options["minimum_autonomy_percent"] = value
    elif parameter == "cost_weights":
        options["selection_weights"] = dict(zip(
            ("eta_weight", "energy_weight", "load_weight"), value))
    elif parameter == "sensor_quality":
        rate = 0.0 if value == "ideal" else 0.3
        for source in result["sources"].values():
            source.update(false_positive_rate=rate, false_negative_rate=rate)
    elif parameter == "reputation_prior":
        settings["reputation"].update(alpha=value, beta=value)
    elif parameter in ("patrol_threshold", "ranger_threshold"):
        settings["policy"][parameter] = value
    elif parameter == "source_diversity":
        settings["policy"].update(ranger_min_groups=value, ranger_min_modalities=value)
    elif parameter == "severity":
        settings["severity"] = value
    elif parameter == "adjudication_distance":
        settings["adjudication"]["max_distance"] = value
    elif parameter == "adjudication_delay":
        settings["adjudication"]["max_delay_seconds"] = value
    validate_configuration(result, options)
    return result, options


def validate_configuration(config, options):
    """Validar cenário e opções do runner antes de simular; levanta erro se inválidos.

    Além do esquema do cenário, constrói a política e a reputação e passa cada episódio
    por ``scenario_settings``, para que os erros surjam antes da recolha.

    Args:
        config (dict): Cenário completo (com ``base_seed``, ``response_settings`` e ``episodes``).
        options (dict): Opções extra do runner.

    Raises:
        ValueError: Se ``base_seed`` não for inteiro, ou se o cenário, a política, a reputação
            ou as opções forem rejeitados pelos validadores.
    """
    validate_scenario(config)
    if type(config["base_seed"]) is not int:
        raise ValueError("base_seed deve ser inteiro.")
    ResponsePolicy(**config["response_settings"]["policy"])
    ReputationBook(**config["response_settings"]["reputation"])
    for episode in config["episodes"]:
        scenario_settings({"run_id": "preflight", "seed": config["base_seed"],
                           "sources": config["sources"], "resources": config["resources"],
                           "events": episode["events"]})
    validate_runner_options(options)


def compare_rows(actual, expected, *, identity):
    """Comparar todos os indicadores comuns; N/A e arredondamentos são explícitos.

    A referência (``expected``) define os campos comparados; campos extra em ``actual`` são
    ignorados. Números comparam-se com tolerância de 1e-10.

    Args:
        actual (list[dict]): Linhas obtidas.
        expected (list[dict]): Linhas de referência.
        identity (tuple[str, ...]): Campos que identificam cada linha nos dois lados.

    Returns:
        list[dict]: Uma diferença por campo divergente ou linha em falta, com ``identity``,
            ``field``, ``actual`` e ``expected``; vazia se coincidirem.

    Raises:
        ValueError: Se uma identidade se repetir em qualquer dos lados.
    """
    def key(row):
        """Devolver a identidade da linha: os campos de ``identity`` em texto."""
        return tuple(str(row[name]) for name in identity)

    def same(left, right):
        """Comparar dois valores: N/A só com N/A, números por ``isclose``, o resto em texto."""
        if left is None or right is None or left == "N/A" or right == "N/A":
            return left in (None, "N/A") and right in (None, "N/A")
        if isinstance(left, bool) or right in ("True", "False"):
            return str(left) == str(right)
        try:
            return math.isclose(float(left), float(right), rel_tol=1e-10, abs_tol=1e-10)
        except (TypeError, ValueError):
            return str(left) == str(right)

    actual_map, expected_map = {}, {}
    for rows, indexed in ((actual, actual_map), (expected, expected_map)):
        for row in rows:
            ident = key(row)
            if ident in indexed:
                raise ValueError(f"Linha duplicada na comparação: {ident}.")
            indexed[ident] = row
    differences = []
    for ident in sorted(actual_map.keys() | expected_map.keys()):
        left, right = actual_map.get(ident), expected_map.get(ident)
        if left is None or right is None:
            differences.append({"identity": ident, "field": "row", "actual": left, "expected": right})
            continue
        # A referência define o contrato de indicadores; extras experimentais não contam.
        for field, expected_value in right.items():
            if field not in left or not same(left[field], expected_value):
                differences.append({"identity": ident, "field": field,
                                    "actual": left.get(field), "expected": expected_value})
    return differences


def read_csv(path):
    """Ler um CSV UTF-8 como lista de dicionários, com todos os valores em texto.

    Args:
        path (Path): Ficheiro a ler.

    Returns:
        list[dict[str, str]]: Uma entrada por linha, pelas colunas do cabeçalho.
    """
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_json(path, value):
    """Gravar JSON indentado num ficheiro novo; falha se já existir ou houver NaN.

    Valores não serializáveis são gravados com ``str``.

    Args:
        path (Path): Ficheiro a criar.
        value (object): Conteúdo a gravar.
    """
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=str, allow_nan=False)
        stream.write("\n")


def write_csv(path, rows):
    """Gravar as linhas num CSV novo, com ``None`` como "N/A".

    As colunas são a união dos campos, pela ordem em que aparecem. Sem linhas não cria
    ficheiro; falha se o ficheiro já existir.

    Args:
        path (Path): Ficheiro a criar.
        rows (list[dict]): Linhas a gravar.
    """
    if not rows:
        return
    fields = list(dict.fromkeys(field for row in rows for field in row))
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: "N/A" if value is None else value for key, value in row.items()}
                         for row in rows)


def create_output(run_id=None):
    """Criar a pasta de saída da recolha.

    A raiz de escrita é fixa e o mkdir exclusivo impede substituir recolhas.

    Args:
        run_id (str | None): Nome da pasta em ``results/sensitivity/``; ``None`` gera um a partir
            da data UTC e de um sufixo aleatório.

    Returns:
        Path: A pasta criada.

    Raises:
        ValueError: Se ``run_id`` não for um nome simples ou se a raiz de resultados for um
            atalho para outro diretório.
    """
    name = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex[:8]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) or name in (".", ".."):
        raise ValueError("--run-id deve ser um nome simples, sem diretórios.")
    if OUTPUT_ROOT.resolve() != OUTPUT_ROOT.absolute():
        raise ValueError("A raiz de resultados não pode redirecionar para outro diretório.")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_ROOT / name
    output.mkdir(exist_ok=False)
    return output


def provenance():
    """Descrever o código e o ambiente usados na recolha.

    Inclui commit, ramo, alterações sem commit, versões de Python e SPADE, plataforma e
    SHA-256 das fontes, cenários, ``requirements.txt`` e ficheiros de referência.

    Returns:
        dict: ``commit``, ``branch``, ``dirty``, ``git_status``, ``python``, ``platform``,
            ``spade``, ``sha256`` (por ficheiro: fontes ``src``, este script,
            ``config/**/*.json`` e ``requirements.txt``) e ``reference_sha256``.
    """
    def git(*args):
        """Correr ``git`` na raiz do repositório e devolver o stdout aparado."""
        return subprocess.run(["git", *args], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()

    files = sorted({*ROOT.glob("src/**/*.py"), ROOT / "scripts/sensitivity.py",
                    *ROOT.glob("config/**/*.json"), ROOT / "requirements.txt"})
    hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in files}
    status = git("status", "--porcelain", "--", "src", "config", "scripts", "tests")
    return {"commit": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"),
            "dirty": bool(status), "git_status": status,
            "python": sys.version, "platform": platform.platform(),
            "spade": importlib.metadata.version("spade"), "sha256": hashes,
            "reference_sha256": {name: hashlib.sha256((REFERENCE_ROOT / name).read_bytes()).hexdigest()
                                 for name in ("runs.csv", "summary.csv", "manifest.json")}}


async def self_check(mode, configs, output):
    """Comparar a referência por execução e, no modo completo, por agregado.

    No modo ``initial`` corre só a primeira repetição do cenário A e compara-a com
    ``runs.csv``; no ``full`` corre os cenários todos e compara execuções, ordem e resumo.
    Grava ``actual.csv`` (e ``actual-runs.csv``) e ``comparison.json`` em ``output``.

    Args:
        mode (str): ``"initial"`` ou ``"full"``.
        configs (list[dict]): Cenários a correr; ignorado no modo ``initial``.
        output (Path): Pasta do self-check.

    Returns:
        dict: Resultado com ``passed``, ``run_count``, ``differences`` e, no modo ``full``, as
            comparações por execução e por resumo.

    Raises:
        ValueError: Se a referência gravada não tiver as sementes, episódios ou ordem da Etapa 9.
    """
    actual, expected, run_count = [], [], 0
    actual_runs, expected_runs, order_differences = [], [], []
    run_identity = ("scenario", "variant", "repetition", "episode", "seed")
    if mode == "initial":
        configs = [load_scenario(SCENARIO_ROOT / "A.json")]
        reference = read_csv(REFERENCE_ROOT / "runs.csv")
        # A primeira repetição começa no prior original e mantém a ordem dos episódios.
        expected = [row for row in reference if row["scenario"] == "A"
                    and row["variant"] == "full" and row["repetition"] == "0"]
        for row in expected:
            if int(row["seed"]) != configs[0]["base_seed"]:
                raise ValueError("Semente da referência inicial diverge do cenário A.")
        identity = run_identity
    else:
        selected = {config["scenario_id"] for config in configs}
        expected = [row for row in read_csv(REFERENCE_ROOT / "summary.csv")
                    if row["variant"] == "full" and row["scenario"] in selected]
        identity = ("scenario", "variant")
        reference_runs = read_csv(REFERENCE_ROOT / "runs.csv")
        for config in configs:
            stored = [row for row in reference_runs if row["scenario"] == config["scenario_id"]
                      and row["variant"] == "full"]
            planned = [(str(rep), episode["label"], str(config["base_seed"] + rep))
                       for rep in range(config["repetitions"]) for episode in config["episodes"]]
            if [(row["repetition"], row["episode"], row["seed"]) for row in stored] != planned:
                raise ValueError("A referência completa exige a mesma ordem, episódios e sementes da Etapa 9.")
            expected_runs.extend(stored)
    for config in configs:
        rows = await run_scenario(config, "full", repetitions=1 if mode == "initial" else None,
                                  output=output / "runs")
        run_count += len(rows)
        actual.extend(rows if mode == "initial" else [flat_summary(config["scenario_id"], "full", rows)])
        if mode == "full":
            actual_runs.extend(rows)
            stored = [row for row in expected_runs if row["scenario"] == config["scenario_id"]]
            received_order = [tuple(str(row[name]) for name in run_identity) for row in rows]
            expected_order = [tuple(row[name] for name in run_identity) for row in stored]
            if received_order != expected_order:
                order_differences.append({
                    "identity": [config["scenario_id"], "full"], "field": "execution_order",
                    "actual": received_order, "expected": expected_order,
                })
    differences = compare_rows(actual, expected, identity=identity)
    result = {"mode": mode, "passed": not differences, "compared_rows": len(actual),
              "run_count": run_count,
              "differences": differences, "reference": "runs.csv" if mode == "initial" else "summary.csv"}
    if mode == "full":
        run_differences = compare_rows(actual_runs, expected_runs, identity=run_identity)
        run_differences.extend(order_differences)
        result["run_comparison"] = {
            "passed": not run_differences, "compared_rows": len(actual_runs),
            "differences": run_differences, "reference": "runs.csv",
        }
        result["summary_comparison"] = {
            "passed": not differences, "compared_rows": len(actual),
            "differences": differences, "reference": "summary.csv",
        }
        result["passed"] = not run_differences and not differences
        result["differences"] = [
            {"level": level, **difference}
            for level, items in (("runs", run_differences), ("summary", differences))
            for difference in items
        ]
        result["references"] = ["runs.csv", "summary.csv"]
        write_csv(output / "actual-runs.csv", actual_runs)
    write_csv(output / "actual.csv", actual)
    write_json(output / "comparison.json", result)
    return result


def plan_experiments(configs, parameters, value=UNSET, repetitions=None):
    """Construir o plano: um item por parâmetro, alternativa e cenário.

    Cada item traz a configuração aplicada, ou o estado ``blocked``/``invalid`` com o
    motivo, e as repetições, sementes e episódios previstos.

    Args:
        configs (list[dict]): Cenários originais.
        parameters (list[str]): Fatores a incluir.
        value (object): Restringe o plano a uma alternativa; ``UNSET`` inclui todas.
        repetitions (int | None): Repetições por cenário; ``None`` usa as do cenário.

    Returns:
        list[dict]: Itens com ``parametro``, ``valor``, ``cenario``, ``status``, ``repetitions``,
            ``seeds``, ``episodes``, ``runs`` e ainda ``config`` e ``runner_options`` (se
            ``ready``) ou ``reason`` (se não).

    Raises:
        ValueError: Se nenhuma alternativa corresponder a ``value``.
    """
    plan = []
    for parameter in parameters:
        for alternative in PARAMETERS[parameter]["alternatives"]:
            if value is not UNSET and not alternative_matches(value, alternative):
                continue
            for original in configs:
                item = {"parametro": parameter, "valor": alternative,
                        "cenario": original["scenario_id"], "status": "ready"}
                try:
                    config, options = apply_experiment(original, parameter, alternative)
                    item.update(config=config, runner_options=options)
                except BlockedExperiment as error:
                    item.update(status="blocked", reason=str(error))
                except (TypeError, ValueError, KeyError) as error:
                    item.update(status="invalid", reason=str(error))
                count = repetitions if repetitions is not None else original["repetitions"]
                item.update(repetitions=count, seeds=list(range(original["base_seed"], original["base_seed"] + count)),
                            episodes=[episode["label"] for episode in original["episodes"]],
                            runs=count * len(original["episodes"]))
                plan.append(item)
    if not plan:
        raise ValueError("Nenhuma alternativa corresponde a --value.")
    return plan


def report_extras(records):
    """Somar os indicadores extra de um grupo de relatórios sobre as execuções.

    Execuções expiradas, contagens por motivo final, recusas por autonomia, missões e
    CFP de rangers e atualizações de reputação.

    Args:
        records (list[dict]): Ficheiros de relatório, com a chave ``report``.

    Returns:
        dict: ``expired_runs``, ``reason_<motivo>`` para quatro motivos,
            ``autonomy_insufficient``, ``ranger_missions_known``, ``ranger_cfp_sent`` e
            ``reputation_updates``.
    """
    reports = [record["report"] for record in records]
    reasons = Counter(report["reason"] for report in reports)
    return {"expired_runs": sum(report["incident_status"] == "expired" for report in reports),
            **{f"reason_{reason}": reasons[reason] for reason in (
                "insufficient_corroboration", "no_eligible_proposals", "confirmation_unknown", "mission_result_unknown")},
            "autonomy_insufficient": sum(entry["body"]["payload"].get("reason") == "autonomy_insufficient"
                                         for report in reports for entry in report["messages"]),
            "ranger_missions_known": sum(mission["task"] == "respond_incident"
                                    for report in reports for mission in report["missions"]),
            "ranger_cfp_sent": sum(entry["body"].get("message_type") == "CFP"
                                   and entry["body"]["payload"].get("task") == "respond_incident"
                                   for report in reports for entry in report["messages"]),
            "reputation_updates": sum(update.get("updated", False)
                                       for report in reports for update in report["reputation_updates"])}


async def collect(plan, configs, repetitions, output):
    """Correr a referência e cada alternativa pronta do plano e gravar os CSV do lote.

    Escreve ``runs.csv``, ``summary.csv`` e as tabelas de calibração, e etiqueta cada
    relatório individual com o fator.

    Args:
        plan (list[dict]): Plano de ``plan_experiments``; itens que não estão ``ready`` são
            saltados.
        configs (list[dict]): Cenários originais, para as referências.
        repetitions (int | None): Repetições por cenário; ``None`` usa as do cenário.
        output (Path): Pasta do lote.

    Returns:
        int: Número total de execuções (referência e alternativas).
    """
    runs, summaries, records = [], [], []
    # Uma trajetória de reputação por cenário e configuração; só run_scenario controla
    # os episódios/repetições. Nunca se filtra um episódio no meio da aprendizagem.
    baselines = [{"parametro": "baseline", "valor": "original", "cenario": config["scenario_id"],
                  "config": deepcopy(config), "runner_options": {}, "status": "ready"}
                 for config in configs]
    for index, item in enumerate([*baselines, *plan]):
        if item["status"] != "ready":
            continue
        run_output = output / "runs" / f"{index:03d}-{item['parametro']}"
        config = item["config"]
        start = time.perf_counter()
        rows = await run_scenario(config, "full", repetitions=repetitions, output=run_output,
                                  runner_options=item["runner_options"])
        elapsed = time.perf_counter() - start
        metadata = {"parametro": item["parametro"], "valor": encoded(item["valor"]),
                    "cenario": item["cenario"]}
        runs.extend({**metadata, **row} for row in rows)
        group_records = []
        for path in sorted(run_output.rglob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            record["metrics"].update(metadata)
            # Só enriquece relatórios acabados de criar nesta recolha exclusiva.
            # A etiqueta persistida separa os fatores numa futura recalibração.
            path.write_text(json.dumps(record, ensure_ascii=False, indent=1, default=str) + "\n",
                            encoding="utf-8")
            group_records.append(record)
        records.extend(group_records)
        summaries.append({**metadata, **flat_summary(item["cenario"], "full", rows),
                          "seeds": encoded(sorted({row["seed"] for row in rows})),
                          "episodes": encoded([episode["label"] for episode in config["episodes"]]),
                          "repetitions": repetitions or config["repetitions"],
                          "tempo_real_total_s": elapsed, "tempo_real_medio_s": elapsed / len(rows),
                          "reputation_sensor_1_final": rows[-1]["reputation_sensor_1"],
                          **report_extras(group_records)})
        print(f"{item['parametro']}={encoded(item['valor'])} / {item['cenario']}: {len(rows)} execuções", flush=True)
    write_csv(output / "runs.csv", runs)
    write_csv(output / "summary.csv", summaries)
    from isia.evaluation.calibration import calibration_tables
    bins, coverage = calibration_tables(records)
    write_csv(output / "calibration.csv", bins)
    write_csv(output / "calibration-coverage.csv", coverage)
    return len(runs)


def main(argv=None):
    """Validar a seleção, correr o self-check e depois as alternativas.

    Depois de gravado o plano e copiado o código, ``manifest.json`` é gravado mesmo em
    caso de falha. Erros de seleção ou de dados antes de criada a pasta de saída terminam
    via ``parser.error``.

    Args:
        argv (list[str] | None): Argumentos da linha de comandos; ``None`` usa ``sys.argv``.

    Returns:
        int: 0 em sucesso e 1 se a seleção não for executável ou a referência divergir.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parameter", choices=sorted(PARAMETERS))
    parser.add_argument("--value", help="Uma alternativa em JSON: 1, 0.1, [0,1,0] ou ideal/noisy")
    parser.add_argument("--scenario", nargs="+", choices=("A", "B", "C"), default=["A", "B", "C"])
    parser.add_argument("--repetitions", type=int)
    parser.add_argument("--self-check", choices=("initial", "full"))
    parser.add_argument("--calibrate-from", type=Path,
                        help="Ler relatórios existentes full; produzir apenas calibração, sem simular")
    parser.add_argument("--run-id", help="Nome exclusivo dentro de results/sensitivity/")
    parser.add_argument("--dry-run", action="store_true", help="Validar o plano sem simular nem gravar")
    parser.add_argument("--list", action="store_true", help="Mostrar catálogo, incluindo alternativas bloqueadas")
    args = parser.parse_args(argv)
    if args.list:
        print(json.dumps({"parameters": PARAMETERS, "blocked": {"source_diversity=1": BLOCKED_DIVERSITY}},
                         ensure_ascii=False, indent=2))
        return 0
    if args.value is not None and args.parameter is None:
        parser.error("--value exige --parameter.")
    if args.calibrate_from and (args.self_check or args.parameter or args.value is not None
                               or args.repetitions is not None):
        parser.error("--calibrate-from não aceita experiências nem self-check.")
    if args.self_check and (args.parameter or args.value is not None or args.repetitions is not None):
        parser.error("--self-check não aceita overrides nem --repetitions; full compara toda a referência.")
    if len(args.scenario) != len(set(args.scenario)):
        parser.error("Não repetir cenários.")
    value = UNSET
    if args.value is not None:
        try:
            value = json.loads(args.value)
        except json.JSONDecodeError:
            value = args.value
    try:
        configs = [load_scenario(SCENARIO_ROOT / f"{name}.json") for name in args.scenario]
        for config in configs:
            validate_configuration(config, {})
            if args.repetitions is not None and not 1 <= args.repetitions <= config["repetitions"]:
                raise ValueError("--repetitions deve estar entre 1 e as 20 repetições originais.")
        plan = [] if args.self_check or args.calibrate_from else plan_experiments(
            configs, [args.parameter] if args.parameter else list(PARAMETERS), value, args.repetitions)
        no_runnable = bool(plan) and not any(item["status"] == "ready" for item in plan)
        stopped_status = ("blocked" if all(item["status"] == "blocked" for item in plan)
                          else "invalid") if no_runnable else None
        calibration_records, calibration_inputs = [], []
        if args.calibrate_from:
            selected = set(args.scenario)
            for path in sorted(args.calibrate_from.rglob("*.json")):
                record = json.loads(path.read_text(encoding="utf-8"))
                metrics = record.get("metrics", {})
                if metrics.get("variant") == "full" and metrics.get("scenario") in selected:
                    calibration_records.append(record)
                    calibration_inputs.append({"path": str(path.resolve()),
                                               "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            if not calibration_records:
                raise ValueError("Não há relatórios full nos cenários selecionados.")
        if args.dry_run:
            print(json.dumps({"status": stopped_status or "planned",
                              "self_check": None if args.calibrate_from or no_runnable else args.self_check or "initial (automático)",
                              "calibration_reports": len(calibration_records), "plan": plan},
                             ensure_ascii=False, indent=2))
            return 1 if no_runnable else 0
        source = provenance()
        output = create_output(args.run_id)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.error(str(error))
    manifest = {"status": "running", "created_at": datetime.now(timezone.utc).isoformat(),
                "argv": argv if argv is not None else sys.argv[1:], "provenance": source,
                "variant": "full", "extensions_bloco_f": "disabled",
                "plan": plan, "repetitions_override": args.repetitions,
                "scenarios": configs, "run_order": "repetition -> episode (ordem do JSON)"}
    if args.calibrate_from:
        manifest["calibration_inputs"] = calibration_inputs
    if no_runnable:
        manifest.update(status=stopped_status, runs=0, baseline_runs=0,
                        alternative_runs=0, total_simulations=0,
                        reason="A seleção não contém alternativas executáveis.")
    write_json(output / "plan.json", manifest)
    if no_runnable:
        write_json(output / "manifest.json", manifest)
        label = "bloqueada" if stopped_status == "blocked" else "inválida"
        print(f"Seleção {label}: nenhuma simulação executada. Plano: {output}", flush=True)
        for reason in dict.fromkeys(item["reason"] for item in plan):
            print(reason, flush=True)
        return 1
    # Guardar o código efetivamente usado, mesmo enquanto há alterações sem commit.
    for relative in source["sha256"]:
        target = output / "source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write((ROOT / relative).read_bytes())
    try:
        if args.calibrate_from:
            from isia.evaluation.calibration import calibration_tables
            bins, coverage = calibration_tables(calibration_records)
            write_csv(output / "calibration.csv", bins)
            write_csv(output / "calibration-coverage.csv", coverage)
            manifest.update(status="complete", runs=0, calibration_reports=len(calibration_records))
            print(f"Calibração de {len(calibration_records)} relatórios existentes: {output}", flush=True)
            return 0
        check_output = output / "self-check"
        check_output.mkdir()
        result = asyncio.run(self_check(args.self_check or "initial", configs, check_output))
        manifest["self_check"] = result
        manifest["total_simulations"] = result["run_count"]
        if not result["passed"]:
            manifest["status"] = "reference_mismatch"
            print(f"Referência divergente; consultar {check_output / 'comparison.json'}. Nenhuma alternativa executada.")
            return 1
        manifest["runs"] = 0 if args.self_check else asyncio.run(collect(plan, configs, args.repetitions, output))
        manifest["baseline_runs"] = 0 if args.self_check else sum(
            (args.repetitions or config["repetitions"]) * len(config["episodes"]) for config in configs)
        manifest["alternative_runs"] = manifest["runs"] - manifest["baseline_runs"]
        manifest["total_simulations"] += manifest["runs"]
        manifest["status"] = "complete" if all(item["status"] == "ready" for item in plan) else "complete_with_blocked"
        print(f"Resultados: {output}", flush=True)
        return 0
    except Exception as error:
        manifest.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        write_json(output / "manifest.json", manifest)


if __name__ == "__main__":
    raise SystemExit(main())

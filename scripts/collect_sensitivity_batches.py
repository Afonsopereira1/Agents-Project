"""Recolher combinações em falta, com um processo e uma validação por lote.

PYTHONPATH=src python scripts/collect_sensitivity_batches.py LOTE_EXISTENTE...
Não retoma episódios: cada lote mantém a trajetória completa da reputação.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

try:
    from scripts import sensitivity
    from scripts.consolidate_sensitivity import load_batches, _key
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import sensitivity
    from consolidate_sensitivity import load_batches, _key


def missing_jobs(paths):
    """Listar as combinações parâmetro/cenário ainda sem alternativas concluídas.

    Exclui ``source_diversity=1``, que está bloqueada, e só olha para os cenários A, B e C.

    Args:
        paths (list[Path]): Pastas dos lotes já concluídos (pelo menos duas), em
            ``results/sensitivity/``.

    Returns:
        tuple[list[dict], dict, list[dict]]: Os lotes validados (saída de ``load_batches``), a
            proveniência comum, e uma tarefa por parâmetro/cenário com ``parameter``,
            ``scenario`` e os ``values`` em falta.

    Raises:
        ValueError: Se o código ou o ambiente atual diferir da proveniência dos lotes existentes.
    """
    batches, signature, completed = load_batches(paths)
    current = sensitivity.provenance()
    if any(current[key] != value for key, value in signature.items()):
        raise ValueError("O código/ambiente atual não corresponde aos lotes existentes.")
    jobs = []
    for parameter, spec in sensitivity.PARAMETERS.items():
        for scenario in ("A", "B", "C"):
            values = [value for value in spec["alternatives"]
                      if not (parameter == "source_diversity" and value == 1)
                      and _key(parameter, value, scenario) not in completed]
            if values:
                jobs.append({"parameter": parameter, "scenario": scenario, "values": values})
    return batches, signature, jobs


def validate_batch(anchor, directory):
    """Conferir CSV, plano, relatórios e sequência sem executar novas simulações.

    Args:
        anchor (Path): Um lote existente, para ``load_batches`` validar o novo em conjunto.
        directory (Path): Pasta do lote acabado de gerar.

    Returns:
        dict: ``status``, ``reports``, ``runs``, ``alternatives`` e ``total_simulations`` do
            lote, e ``baseline_differences`` (diferenças da linha de base face a
            ``runs.csv`` publicado; vazia se coincidir).

    Raises:
        ValueError: Se o plano e o manifesto diferirem, ou se os relatórios JSON divergirem do CSV.
    """
    batches, signature, groups = load_batches([anchor, directory])
    batch = batches[-1]
    manifest = json.loads((directory / "manifest.json").read_text())
    plan = json.loads((directory / "plan.json").read_text())
    for key in ("plan", "scenarios", "provenance", "repetitions_override", "run_order"):
        if plan[key] != manifest[key]:
            raise ValueError(f"{directory.name}: plano e manifesto diferem em {key}.")
    records = [json.loads(path.read_text()) for path in (directory / "runs").rglob("*.json")]
    identity = ("parametro", "valor", "scenario", "variant", "repetition", "episode", "seed")
    differences = sensitivity.compare_rows([record["metrics"] for record in records], batch["runs"],
                                          identity=identity)
    if differences:
        raise ValueError(f"{directory.name}: relatórios e CSV divergem: {differences[:2]}.")
    published = [row for row in sensitivity.read_csv(sensitivity.REFERENCE_ROOT / "runs.csv")
                 if row["variant"] == "full" and row["scenario"] == manifest["scenarios"][0]["scenario_id"]]
    baseline = [row for row in batch["runs"] if row["parametro"] == "baseline"]
    return {"status": manifest["status"], "reports": len(records), "runs": len(batch["runs"]),
            "alternatives": manifest["alternative_runs"], "total_simulations": manifest["total_simulations"],
            "baseline_differences": sensitivity.compare_rows(baseline, published,
                identity=("scenario", "variant", "repetition", "episode", "seed"))}


def main(argv=None):
    """Correr ``scripts/sensitivity.py`` num processo por tarefa e validar cada lote.

    O estado fica em ``collection.json`` na pasta nova e a saída de cada processo em
    ``NN.log``; com ``--dry-run`` só imprime as tarefas. Uma falha fica registada como
    ``failed`` e é relançada. Erros nos argumentos ou nos lotes de entrada terminam via
    ``parser.error``.

    Args:
        argv (list[str] | None): Argumentos da linha de comandos; ``None`` usa ``sys.argv``.

    Returns:
        int: 0 quando a recolha (ou o ``--dry-run``) termina sem erros.

    Raises:
        ValueError: Se a proveniência mudar durante a recolha ou se a validação de um lote
            novo falhar.
        RuntimeError: Se o processo de um lote terminar com código diferente de 0.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("existing", nargs="+", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, help="Executar só os primeiros N lotes para validação")
    args = parser.parse_args(argv)
    try:
        if args.limit is not None and args.limit < 1:
            raise ValueError("--limit deve ser positivo.")
        batches, signature, jobs = missing_jobs(args.existing)
        if args.limit is not None:
            jobs = jobs[:args.limit]
        if args.dry_run:
            print(json.dumps(jobs, ensure_ascii=False, indent=2))
            return 0
        output = sensitivity.create_output(args.run_id)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    state = {"status": "running", "provenance": signature,
             "created_at": datetime.now(timezone.utc).isoformat(),
             "existing": [batch["path"] for batch in batches], "jobs": jobs}
    # Este checkpoint pertence apenas à nova pasta; nunca se escreve nos lotes de entrada.
    def checkpoint():
        """Regravar ``collection.json`` com o estado atual da recolha."""
        (output / "collection.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    checkpoint()
    try:
        for index, job in enumerate(jobs):
            # Verificar de novo antes de cada processo: nenhuma alteração de código a meio.
            current = sensitivity.provenance()
            if any(current[key] != value for key, value in signature.items()):
                raise ValueError("A proveniência mudou durante a recolha.")
            name = f"g-final-{job['parameter']}-{job['scenario']}-{uuid4().hex[:8]}"
            command = [sys.executable, str(sensitivity.ROOT / "scripts/sensitivity.py"),
                       "--parameter", job["parameter"], "--scenario", job["scenario"], "--run-id", name]
            if len(job["values"]) == 1:
                command += ["--value", sensitivity.encoded(job["values"][0])]
            job.update(status="running", output=str(sensitivity.OUTPUT_ROOT / name), command=command)
            checkpoint()
            started = time.perf_counter()
            with (output / f"{index:02d}.log").open("x") as stream:
                process = subprocess.run(command, cwd=sensitivity.ROOT, stdout=stream,
                                         stderr=subprocess.STDOUT, text=True)
            job.update(returncode=process.returncode, seconds=time.perf_counter() - started)
            if process.returncode:
                raise RuntimeError(f"O lote {name} terminou com código {process.returncode}; ver {index:02d}.log.")
            job["validation"] = validate_batch(Path(batches[0]["path"]), Path(job["output"]))
            job["status"] = "complete"
            checkpoint()
            print(json.dumps({"completed": index + 1, "planned": len(jobs), **job}, ensure_ascii=False), flush=True)
        state["status"] = "complete"
    except BaseException as error:
        state.update(status="failed", error=f"{type(error).__name__}: {error}")
        if "job" in locals() and job.get("status") == "running":
            job["status"] = "failed"
        raise
    finally:
        checkpoint()
    print(f"Recolha validada: {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

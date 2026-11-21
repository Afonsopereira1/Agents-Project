"""Bloco F2, execução longa: N execuções seguidas com a mesma reputação (C8, reputação).

Cenário A (1 caçador em (3,2)), política completa, sementes 1000+i. A cada 100
execuções grava uma linha em results/stress/longa.csv com o tamanho de
book.history e a memória do processo. rss_pico_kb é o pico do processo (Linux, kB)
e inclui o interpretador; history_json_kb é só o histórico serializado.
Uso, a partir da raiz: PYTHONPATH=src python scripts/stress_long.py [N=1000]
"""
import asyncio, copy, csv, json, resource, sys, time
from pathlib import Path

from isia.evaluation.collector import load_scenario
from isia.evaluation.metrics import run_metrics
from isia.reasoning.reputation import ReputationBook
from isia.simulation.runner import PUBLISHED_CONDITIONS, run_mvp

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "stress" / "longa.csv"
base = load_scenario(ROOT / "config" / "scenarios" / "A.json")
FIELDS = ["execucoes", "history_registos", "history_json_kb", "rss_pico_kb", "reputacao_sensor_1",
          "confirmou", "unresolved", "tempo_real_s"]

async def go():
    """Correr ``N`` execuções com o mesmo ``ReputationBook`` e gravar ``longa.csv``."""
    s = copy.deepcopy(base["response_settings"])
    book = ReputationBook(**s["reputation"])
    out, confirmed, unresolved, t0 = [], 0, 0, time.monotonic()
    def line(done):
        """Acrescentar e imprimir uma linha de medição após ``done`` execuções."""
        out.append({"execucoes": done, "history_registos": len(book.history),
                    "history_json_kb": round(len(json.dumps(book.history, default=str)) / 1024, 1),
                    "rss_pico_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                    "reputacao_sensor_1": round(book.score("sensor-1"), 4), "confirmou": confirmed,
                    "unresolved": unresolved, "tempo_real_s": round(time.monotonic() - t0, 1)})
        print(out[-1], flush=True)
    line(0)
    for i in range(N):
        report = await run_mvp(response_settings=s, reputation=book, max_seconds=30.0, **PUBLISHED_CONDITIONS,
            scenario={"run_id": f"longa-{i:04d}", "seed": 1000 + i, "sources": base["sources"],
                      "events": base["episodes"][0]["events"], "resources": base["resources"]})
        row = run_metrics(report)
        confirmed += row["confirmed"]; unresolved += row["unresolved"]
        if (i + 1) % 100 == 0 or i + 1 == N:
            line(i + 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS, lineterminator="\n"); w.writeheader(); w.writerows(out)
    print("gravado:", OUT.relative_to(ROOT))

if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    asyncio.run(go())

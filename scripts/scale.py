"""P3, custo computacional: mensagens e tempo real ao retirar recursos ou juntar caçadores.

Cenário A, variante full, 10 repetições (sementes 1000–1009). Grava
results/scalability/scale.csv. O tempo real depende da máquina; compare
casos da mesma execução, não valores absolutos entre máquinas.
Uso, a partir da raiz: PYTHONPATH=src python scripts/scale.py
"""
import asyncio, collections, copy, csv, time
from pathlib import Path

from isia.evaluation.collector import load_scenario, run_scenario
from isia.evaluation.metrics import summarize

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "scalability" / "scale.csv"
base = load_scenario(ROOT / "config" / "scenarios" / "A.json")
threat = base["episodes"][0]
def ev(i, x, y): return {**threat["events"][0], "event_id": f"threat-{i:02d}", "position": {"x": x, "y": y}}
CASES = {
  "base: 2 patrulhas + 1 guarda, 1 caçador": (None, [ev(1, 3, 2)]),
  "-drone silencioso (1 patrulha)": ({"unavailable_agents": ["drone-mvp"]}, [ev(1, 3, 2)]),
  "0 patrulhas": ({"unavailable_agents": ["drone-mvp", "vehicle-mvp"]}, [ev(1, 3, 2)]),
  "0 guardas": ({"unavailable_agents": ["ranger-mvp"]}, [ev(1, 3, 2)]),
  "3 caçadores": (None, [ev(1, 3, 2), ev(2, 6, 6), ev(3, 1, 6)]),
}
FIELDS = ["caso", "runs", "TP", "FN", "confirmed_runs", "unresolved_runs", "t_verif_mean", "t_resp_mean",
          "msgs_mean", "msgs_por_execucao", "energia_mean", "tempo_real_s", "motivos"]

async def go():
    out = []
    for name, (faults, events) in CASES.items():
        c = copy.deepcopy(base); c["faults"] = faults
        c["episodes"] = [{"label": "t", "events": events}]
        t0 = time.monotonic()
        rows = await run_scenario(c, "full", repetitions=10)
        s = summarize(rows)
        msgs = collections.Counter(r["messages_sent"] for r in rows)
        out.append({"caso": name, "runs": s["runs"], "TP": s["TP"], "FN": s["FN"],
                    "confirmed_runs": s["confirmed_runs"], "unresolved_runs": s["unresolved_runs"],
                    "t_verif_mean": s["verification_time"]["mean"], "t_resp_mean": s["response_time"]["mean"],
                    "msgs_mean": s["messages_sent"]["mean"],
                    "msgs_por_execucao": " ".join(f"{k}x{v}" for k, v in sorted(msgs.items())),
                    "energia_mean": s["energy_used"]["mean"], "tempo_real_s": round(time.monotonic() - t0, 1),
                    "motivos": " ".join(f"{k}={v}" for k, v in collections.Counter(r["reason"] for r in rows).items())})
        print(out[-1])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS); w.writeheader(); w.writerows(out)
    print("gravado:", OUT.relative_to(ROOT))

asyncio.run(go())

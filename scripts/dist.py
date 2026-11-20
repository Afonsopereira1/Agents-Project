"""P3, escalabilidade situacional: distribuição de caçadores e recursos (cenário A, variante full).

Sementes 1000–1009 (10 repetições); casos com perdas usam 20. Grava
results/scalability/dist.csv. «Atendidos» conta ameaças reais confirmadas por
uma patrulha na sua posição (métrica por caçador, não por execução).
Uso, a partir da raiz: PYTHONPATH=src python scripts/dist.py
"""
import asyncio, collections, copy, csv
from pathlib import Path

from isia.evaluation.collector import load_scenario
from isia.evaluation.metrics import run_metrics
from isia.reasoning.reputation import ReputationBook
from isia.simulation.runner import PUBLISHED_CONDITIONS, run_mvp

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "scalability" / "dist.csv"
base = load_scenario(ROOT / "config" / "scenarios" / "A.json")
T = base["episodes"][0]["events"][0]
def ev(i, x, y):
    """Copiar a ameaça base do cenário A com o id ``threat-NN`` e a posição (x, y).

    Args:
        i (int): Número da ameaça, usado no id (``threat-01``, …).
        x (int): Coluna da ameaça, em células.
        y (int): Linha da ameaça, em células.

    Returns:
        dict: Evento de ameaça pronto a pôr num episódio.
    """
    return {**T, "event_id": f"threat-{i:02d}", "position": {"x": x, "y": y}}
def pos(x, y):
    """Criar um override de recurso que só fixa a posição (x, y).

    Args:
        x (int): Coluna, em células.
        y (int): Linha, em células.

    Returns:
        dict: ``{"position": {"x": x, "y": y}}``.
    """
    return {"position": {"x": x, "y": y}}
LOSS = {"loss": 0.1, "delay": {"PROPOSAL": 0.05, "MISSION_RESULT": 0.05}, "duplicate": ["MISSION_RESULT"]}
CASES = [
 ("P-a 1 caçador perto (3,2)", [ev(1, 3, 2)], {}, None, 10),
 ("P-b 1 caçador (2,5)", [ev(1, 2, 5)], {}, None, 10),
 ("P-c 1 caçador (7,0) só sensor-2 alcança", [ev(1, 7, 0)], {}, None, 10),
 ("P-d 1 caçador (6,6) fora de alcance", [ev(1, 6, 6)], {}, None, 10),
 ("P-e 2 caçadores (3,2)+(2,5)", [ev(1, 3, 2), ev(2, 2, 5)], {}, None, 10),
 ("P-f 3 caçadores (3,2)+(2,5)+(6,6)", [ev(1, 3, 2), ev(2, 2, 5), ev(3, 6, 6)], {}, None, 10),
 ("R-a recursos base", [ev(1, 3, 2)], {"drone": {"load": 0.5}}, None, 10),
 ("R-b recursos longe (canto 7,7)", [ev(1, 3, 2)], {"drone": {**pos(7, 7), "load": 0.5}, "vehicle": pos(7, 6), "ranger": pos(7, 7)}, None, 10),
 ("R-c ranger longe (0,7)", [ev(1, 3, 2)], {"drone": {"load": 0.5}, "ranger": pos(0, 7)}, None, 10),
 ("R-d drone 15% (1 patrulha útil)", [ev(1, 3, 2)], {"drone": {"autonomy_percent": 15.0}}, None, 10),
 ("R-e drone e veículo 15% (0 úteis)", [ev(1, 3, 2)], {"drone": {"autonomy_percent": 15.0}, "vehicle": {"autonomy_percent": 15.0}}, None, 10),
 ("F-a perdas 10% + 2 patrulhas úteis", [ev(1, 3, 2)], {"drone": {"load": 0.5}}, LOSS, 20),
 ("F-b perdas 10% + 1 patrulha útil", [ev(1, 3, 2)], {"drone": {"autonomy_percent": 15.0}}, LOSS, 20),
]
FIELDS = ["caso", "runs", "alerta", "mobilizou", "confirmou", "unresolved", "atendidos", "ameacas",
          "t_verif_mean", "t_guarda_mean", "energia_mean", "motivos"]

def attended(report):
    """Devolver (ameaças reais confirmadas por patrulha na sua posição, total).

    Uma ameaça conta como atendida se houver um ``verify_incident`` com resultado
    ``confirmed`` exatamente na posição dela.

    Args:
        report (dict): Relatório de uma execução de ``run_mvp``.

    Returns:
        tuple[int, int]: Ameaças reais atendidas e total de ameaças reais.
    """
    threats = [e for e in report["ground_truth"]["events"] if e["is_threat"]]
    ok = {(r["payload"]["position"]["x"], r["payload"]["position"]["y"]) for r in report["results"]
          if r["payload"]["task"] == "verify_incident" and r["payload"]["outcome"] == "confirmed"}
    return sum((e["position"]["x"], e["position"]["y"]) in ok for e in threats), len(threats)

# Self-check da métrica por caçador: duas ameaças, só uma confirmada.
assert attended({"ground_truth": {"events": [{"is_threat": True, "position": {"x": 3, "y": 2}},
                                             {"is_threat": True, "position": {"x": 2, "y": 5}}]},
                 "results": [{"payload": {"task": "verify_incident", "outcome": "confirmed",
                                          "position": {"x": 3, "y": 2}}}]}) == (1, 2)

def mean(rows, key):
    """Calcular a média de ``key`` nas linhas com valor, a 1 casa; ``None`` se não houver.

    Args:
        rows (list[dict]): Métricas por execução (saída de ``run_metrics``).
        key (str): Métrica a agregar; valores ``None`` são ignorados.

    Returns:
        float | None: Média arredondada a 1 casa, ou ``None`` se nenhuma linha tiver valor.
    """
    values = [r[key] for r in rows if r[key] is not None]
    return round(sum(values) / len(values), 1) if values else None

async def go():
    """Correr os ``CASES`` com reputação nova por execução e gravar ``dist.csv``."""
    s = copy.deepcopy(base["response_settings"])
    out = []
    for name, events, res, faults, reps in CASES:
        rows, att, tot = [], 0, 0
        for rep in range(reps):
            seed = 1000 + rep
            report = await run_mvp(response_settings=s, reputation=ReputationBook(**s["reputation"]), **PUBLISHED_CONDITIONS,
                faults=None if faults is None else {**faults, "seed": seed}, max_seconds=30.0,
                scenario={"run_id": f"d-{rep}", "seed": seed, "sources": base["sources"], "events": events, "resources": res})
            rows.append(run_metrics(report)); a, t = attended(report); att += a; tot += t
        out.append({"caso": name, "runs": reps, "alerta": sum(r["alert"] for r in rows),
                    "mobilizou": sum(r["dispatched"] for r in rows), "confirmou": sum(r["confirmed"] for r in rows),
                    "unresolved": sum(r["unresolved"] for r in rows), "atendidos": att, "ameacas": tot,
                    "t_verif_mean": mean(rows, "verification_time"), "t_guarda_mean": mean(rows, "response_time"),
                    "energia_mean": mean(rows, "energy_used"),
                    "motivos": " ".join(f"{k}={v}" for k, v in collections.Counter(r["reason"] for r in rows).items())})
        print(out[-1])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS); w.writeheader(); w.writerows(out)
    print("gravado:", OUT.relative_to(ROOT))

asyncio.run(go())

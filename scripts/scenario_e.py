"""Cenário E: comparar as ocorrências corroboradas por câmaras com as corroboradas por informadores humanos.

Lê os relatórios de results/scenario-e/runs/ (gravados pelo coletor) e grava results/scenario-e/informants.csv.
Cada iniciador pergunta ao informador mais próximo; o tipo desse informador vem do próprio cenário.
Uso, a partir da raiz, depois do coletor: PYTHONPATH=src python scripts/scenario_e.py
"""
import csv, json
from math import hypot
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "scenario-e"
config = json.loads((ROOT / "config/scenarios/demo/E.json").read_text(encoding="utf-8"))
world = config["world"]
informants = {**{"sensor-2": world["sensors"]["sensor-2"]}, **world["informants"]}
initiators = {**{"sensor-1": world["sensors"]["sensor-1"]}, **world["initiators"]}
# O mesmo critério do runner: o informador mais próximo do iniciador.
kind = {key: config["sources"][min(informants, key=lambda i: hypot(informants[i]["x"] - p["x"], informants[i]["y"] - p["y"]))]["kind"]
        for key, p in initiators.items()}
rows = {k: {"informador": k, "ocorrencias_possiveis": 0, "com_alerta": 0, "corroboradas": 0, "mobilizadas": 0,
            "fechadas_confirmadas": 0, "expiradas": 0, "unresolved": 0} for k in ("visual", "human")}
reports = sorted((OUT / "runs" / "E" / "full").glob("*.json"))
assert reports, "Correr primeiro o coletor com config/scenarios/demo/E.json."
for path in reports:
    report = json.loads(path.read_text(encoding="utf-8"))["report"]
    for key, view in {"sensor-1": report, **report["extra_initiators"]}.items():
        row, decision = rows[kind[key]], view["decision"] or {}
        row["ocorrencias_possiveis"] += 1
        row["com_alerta"] += view["incident_status"] is not None
        row["corroboradas"] += bool(decision.get("compatible_source_ids"))
        row["mobilizadas"] += str(decision.get("decision", "")).startswith("request")
        row["fechadas_confirmadas"] += view["incident_status"] == "closed" and view["reason"] == "confirmed"
        row["expiradas"] += view["incident_status"] == "expired"
        row["unresolved"] += view["incident_status"] == "unresolved"
with (OUT / "informants.csv").open("w", newline="", encoding="utf-8") as stream:
    writer = csv.DictWriter(stream, list(rows["visual"]), lineterminator="\n")
    writer.writeheader(); writer.writerows(rows.values())
for row in rows.values():
    print(row)

"""Repetição de uma execução no terminal, a partir do relatório JSON do run_mvp.

Só lê o relatório: não corre agentes nem toma decisões. Usa a `timeline` (e não
`messages`, que vem vazio em XMPP). Aceita a saída do runner ou um ficheiro de
results/experiments/runs/ (com a chave `report`).
Uso, a partir da raiz:
  PYTHONPATH=src python -m isia.simulation.runner > /tmp/isia-mvp.json
  python scripts/replay.py /tmp/isia-mvp.json [--delay 0.5]
"""
import argparse, json, time
from itertools import groupby

# Mapa do MVP, para relatórios antigos sem a chave `world`; os novos trazem o tamanho e os sensores.
WORLD = {"width": 8, "height": 8, "sensors": {"sensor-1": {"x": 2, "y": 2}, "sensor-2": {"x": 4, "y": 2}}}
MARK = {"drone": "D", "vehicle": "V", "ranger": "R"}
SENT = {"CFP", "ACCEPT", "REJECT"}  # MISSION_RESULT só conta na entrada do sensor (com payload)
LOCAL = {"ALERT", "INCIDENT_CLOSED"}  # ficam no registo do sensor; não são enviadas (protocols.md)


def xy(p):
    return p["x"], p["y"]


def grid(threats, positions, world=WORLD):
    cells = {**{xy(p): "S" for p in world["sensors"].values()}, **{p: "X" for p in threats}}
    for rid, p in positions.items():
        # Recursos adicionais (drone-2, ranger-2) usam a letra do seu tipo.
        cells[p] = "*" if p in cells and cells[p] in "DVR*" else MARK.get(rid.split("-")[0], "?")
    rows = [f"{y} | " + " ".join(cells.get((x, y), ".") for x in range(world["width"]))
            for y in reversed(range(world["height"]))]
    return "\n".join(rows + ["    " + " ".join(str(x % 10) for x in range(world["width"])) + "  x"])


def describe(e):
    sensor = e.get("initiator", "sensor")  # com vários iniciadores, as entradas dos adicionais dizem qual
    who = e.get("resource_id") or e.get("recipient", "").split("-mvp")[0] or sensor
    kind = e["event"]
    if kind == "corroboration":
        d = e["decision"]
        return f"{sensor:<8} corroboração: {d['decision']} ({d['reason']})"
    if kind in LOCAL:
        return f"{sensor:<8} registo local: {kind} {e.get('reason', '')}".rstrip()
    if kind == "MISSION_RESULT" and "payload" not in e:
        return f"{who:<8} estado: resultado enviado ({e['outcome']})"
    if kind in SENT or kind == "MISSION_RESULT":
        extra = e.get("payload", {}).get("outcome") or e.get("payload", {}).get("reason") or e.get("reason") or ""
        arrow = f"{sensor} → {who}" if "recipient" in e else f"{who} → {sensor}"
        return f"msg      {kind:<15} {arrow} {extra}".rstrip()
    if kind == "position":
        return None
    return f"{who:<8} estado: {kind}"


def frames(report):
    positions = {r["resource_id"]: xy(r["position"]) for r in report["initial_resources"]}
    energy = {r["resource_id"]: r["autonomy_percent"] for r in report["initial_resources"]}
    for t, group in groupby(report["timeline"], key=lambda e: e["time"]):
        lines = []
        for e in group:
            if "position" in e and "resource_id" in e:
                positions[e["resource_id"]] = xy(e["position"])
                energy[e["resource_id"]] = e["energy"]
            line = describe(e)
            if line and (not lines or lines[-1] != line):
                lines.append(line)
        yield t, dict(positions), dict(energy), lines


def summary(report):
    tl = report["timeline"]
    sent = sum(e["event"] in SENT or (e["event"] == "MISSION_RESULT" and "payload" in e) for e in tl)
    confirmed = [e["time"] for e in tl if e["event"] == "MISSION_RESULT" and "payload" in e]
    used = {r["resource_id"]: round(r["autonomy_percent"] - s["autonomy_percent"], 1)
            for r, s in zip(report["initial_resources"], report["resources"])}
    return [
        f"estado final: {report['incident_status']} ({report['reason']})",
        *(f"estado final de {key}: {view['incident_status']} ({view['reason']})"
          for key, view in report.get("extra_initiators", {}).items()),
        f"CFP/ACCEPT/REJECT/MISSION_RESULT na timeline: {sent} | "
        f"todas as mensagens no transcrito: {len(report['messages']) or 'N/A (XMPP ou nenhuma)'}",
        f"tempos de MISSION_RESULT (s): {confirmed or 'nenhum'}",
        f"energia gasta por recurso (%): {used}",
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("report", help="JSON do run_mvp ou de results/experiments/runs/")
    parser.add_argument("--delay", type=float, default=0.0, help="Segundos reais entre fotogramas")
    args = parser.parse_args()
    with open(args.report, encoding="utf-8") as stream:
        report = json.load(stream)
    report = report.get("report", report)
    threats = {xy(e["position"]) for e in report["ground_truth"]["events"] if e["is_threat"]}
    print(f"Repetição de {report.get('run_id', args.report)} | transporte {report['transport']}")
    print("S sensor | X ameaça real | D drone | V veículo | R guarda | * vários")
    for t, positions, energy, lines in frames(report):
        print(f"\n=== t = {t:g} s ===")
        print(grid(threats, positions, report.get("world", WORLD)))
        print("energia: " + " ".join(f"{MARK.get(r, r)}={e:g}%" for r, e in energy.items()))
        for line in lines:
            print("  " + line)
        time.sleep(args.delay)
    print("\n=== métricas ===")
    print("\n".join(summary(report)))


# Self-check: posições e mensagens saem só da timeline.
_r = {"initial_resources": [{"resource_id": "drone", "position": {"x": 0, "y": 2}, "autonomy_percent": 100.0}],
      "timeline": [{"time": 0.0, "event": "CFP", "recipient": "drone-mvp@localhost", "payload": {}},
                   {"time": 1.0, "event": "position", "resource_id": "drone", "position": {"x": 1, "y": 2}, "energy": 99.0}]}
_f = list(frames(_r))
assert _f[1][1] == {"drone": (1, 2)} and _f[1][2] == {"drone": 99.0}
assert _f[0][3] == ["msg      CFP             sensor → drone"]
assert grid({(1, 0)}, {"ranger-2": (0, 0)}, {"width": 2, "height": 1, "sensors": {}}) == "0 | R X\n    0 1  x"

if __name__ == "__main__":
    main()

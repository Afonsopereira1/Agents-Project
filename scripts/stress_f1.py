"""Bloco F1: curvas de stress só com parâmetros de faults e scenario (sem código novo).

Cenário A (1 caçador em (3,2)), política completa, reputação nova por execução,
sementes 1000+i. Cada grupo grava results/stress/<grupo>.csv. tempo_real_s
depende da máquina; as restantes colunas devem repetir-se com as mesmas sementes
(a perda aleatória depende também da ordem do asyncio).
Uso, a partir da raiz: PYTHONPATH=src python scripts/stress_f1.py [grupo ...]
Grupos: perda latencia cascata autonomia combinadas
        reenvio (perda de 10, 20 e 30 % sem reenvio e com 1 e 2 reenvios por pedido; não corre por omissão)
"""
import asyncio, collections, copy, csv, sys, time
from pathlib import Path

from isia.evaluation.collector import load_scenario
from isia.evaluation.metrics import run_metrics
from isia.reasoning.reputation import ReputationBook
from isia.simulation.runner import PUBLISHED_CONDITIONS, run_mvp

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "stress"
base = load_scenario(ROOT / "config" / "scenarios" / "A.json")
EVENTS = base["episodes"][0]["events"]
RES = base["resources"]  # drone com carga 0,5
def auto(p):
    """Configurar o drone (carga 0,5) e o veículo, ambos com ``p`` por cento de autonomia.

    Args:
        p (float): Autonomia inicial do drone e do veículo, em %.

    Returns:
        dict: Overrides de recursos para o ``scenario`` do ``run_mvp``.
    """
    return {"drone": {"load": 0.5, "autonomy_percent": p}, "vehicle": {"autonomy_percent": p}}

GROUPS = {
  "perda": [(f"loss={p}", RES, {"loss": p}, 20) for p in (0.0, 0.1, 0.2, 0.3, 0.5)],
  "latencia": [(f"{kind} delay={d}s", RES, {"delay": {kind: d}}, 10)
               for kind in ("PROPOSAL", "STATUS") for d in (0.1, 0.3, 0.4, 0.5, 0.6, 1.0)],
  "cascata": [(name, RES, {"unavailable_agents": off}, 10) for name, off in (
      ("todos", []), ("-drone", ["drone-mvp"]), ("-drone -vehicle", ["drone-mvp", "vehicle-mvp"]),
      ("-ranger", ["ranger-mvp"]), ("-drone -vehicle -ranger", ["drone-mvp", "vehicle-mvp", "ranger-mvp"]))],
  "autonomia": [(f"drone e veículo {p}%", auto(p), None, 10) for p in (100.0, 50.0, 25.0, 20.0, 19.0, 16.0, 15.0, 10.0)],
  "combinadas": [("loss=0.2 + MISSION_RESULT duplicado + drone ocupado", RES,
                  {"loss": 0.2, "duplicate": ["MISSION_RESULT"], "occupied_after_proposal": ["drone"]}, 20)],
  # Reenvio: o limite de 30 s da Etapa 9 não chega para os prazos repetidos; vale o do runner.
  "reenvio": [(f"loss={p} reenvios={n}", RES, {"loss": p}, 20, {"retransmit": n, "max_seconds": None})
              for p in (0.1, 0.2, 0.3) for n in (0, 1, 2)],
}
FIELDS = ["caso", "runs", "alerta", "mobilizou", "confirmou", "closed", "unresolved", "motivos",
          "msgs_mean", "perdidas_mean", "recusas_REJECT", "vencedor_patrulha",
          "duplas_reservas", "fechos_duplicados", "tempo_real_s"]

def double_bookings(report):
    """Contar reservas de um recurso já reservado por outra missão.

    Só conta entradas dos móveis (as que têm posição); reservar de novo para a mesma missão
    não conta.

    Args:
        report (dict): Relatório de uma execução de ``run_mvp``.

    Returns:
        int: Número de duplas reservas na ``timeline``.
    """
    held, count = {}, 0
    for e in report["timeline"]:
        if "position" not in e or e["event"] not in ("reserved", "available"):
            continue
        rid, mission = e["resource_id"], e.get("mission_id")
        if e["event"] == "reserved":
            count += held.get(rid) not in (None, mission)
            held[rid] = mission
        elif held.get(rid) == mission:
            held[rid] = None
    return count

# Self-check: drone reservado por m1 e depois por m2 sem libertar conta uma dupla reserva.
_p = {"x": 0, "y": 0}
assert double_bookings({"timeline": [
    {"event": "reserved", "resource_id": "drone", "mission_id": "m1", "position": _p},
    {"event": "reserved", "resource_id": "drone", "mission_id": "m1", "position": _p},
    {"event": "available", "resource_id": "drone", "mission_id": "m1", "position": _p},
    {"event": "reserved", "resource_id": "drone", "mission_id": "m2", "position": _p},
    {"event": "reserved", "resource_id": "drone", "mission_id": "m3", "position": _p}]}) == 1

def mean(values):
    """Calcular a média dos valores não nulos, a 2 casas; ``None`` se não houver.

    Args:
        values (Iterable[float | None]): Valores a agregar; ``None`` é ignorado.

    Returns:
        float | None: Média arredondada a 2 casas, ou ``None`` se não houver valores.
    """
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 2) if values else None

async def case(name, resources, faults, reps, options=None):
    """Correr ``reps`` execuções de um caso e devolver a linha agregada do CSV.

    Reputação nova por execução e sementes 1000+i; ``options`` sobrepõe-se ao limite de
    30 s e às condições publicadas do runner (por exemplo, ``retransmit``).

    Args:
        name (str): Nome do caso, na coluna ``caso``.
        resources (dict): Overrides dos recursos para o ``scenario``.
        faults (dict | None): Falhas a injetar (sem ``seed``, que é posta por execução);
            ``None`` não injeta nenhuma.
        reps (int): Número de execuções.
        options (dict | None): Argumentos extra do ``run_mvp``.

    Returns:
        dict: Linha do CSV com as colunas de ``FIELDS`` e ainda ``reenvios_mean``.
    """
    s = copy.deepcopy(base["response_settings"])
    rows, rejects, doubles, closes, resent = [], 0, 0, 0, []
    t0 = time.monotonic()
    for rep in range(reps):
        seed = 1000 + rep
        report = await run_mvp(response_settings=s, reputation=ReputationBook(**s["reputation"]),
            faults=None if faults is None else {**faults, "seed": seed},
            **{"max_seconds": 30.0, **PUBLISHED_CONDITIONS, **(options or {})},
            scenario={"run_id": f"f1-{rep}", "seed": seed, "sources": base["sources"],
                      "events": EVENTS, "resources": resources})
        rows.append(run_metrics(report))
        rejects += sum(m["body"]["message_type"] == "REJECT" and not m["sender"].startswith("sensor")
                       for m in report["messages"])
        doubles += double_bookings(report)
        closes += sum(e["event"] == "INCIDENT_CLOSED" for e in report["timeline"]) > 1
        # Reenvio = o mesmo message_id outra vez para o mesmo destinatário.
        resent.append(len(report["messages"]) - len({(m["to"], m["body"]["message_id"]) for m in report["messages"]}))
    count = lambda key: " ".join(f"{k}={v}" for k, v in collections.Counter(r[key] for r in rows).items())
    return {"caso": name, "runs": reps, "alerta": sum(r["alert"] for r in rows),
            "mobilizou": sum(r["dispatched"] for r in rows), "confirmou": sum(r["confirmed"] for r in rows),
            "closed": sum(r["status"] == "closed" for r in rows), "unresolved": sum(r["unresolved"] for r in rows),
            "motivos": count("reason"), "msgs_mean": mean(r["messages_sent"] for r in rows),
            "perdidas_mean": mean(r["messages_lost"] for r in rows), "recusas_REJECT": rejects,
            "vencedor_patrulha": count("first_patrol"), "duplas_reservas": doubles,
            "fechos_duplicados": closes, "tempo_real_s": round(time.monotonic() - t0, 1),
            "reenvios_mean": mean(resent)}

async def go(groups):
    """Correr os grupos indicados e gravar um CSV por grupo em results/stress/.

    Args:
        groups (list[str]): Nomes de grupos de ``GROUPS``, pela ordem a correr.
    """
    OUT.mkdir(parents=True, exist_ok=True)
    for group in groups:
        out = []
        for spec in GROUPS[group]:
            out.append(await case(*spec))
            print(group, out[-1], flush=True)
        path = OUT / f"{group}.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            fields = FIELDS + ["reenvios_mean"] * (group == "reenvio")
            w = csv.DictWriter(f, fields, lineterminator="\n", extrasaction="ignore"); w.writeheader(); w.writerows(out)
        print("gravado:", path.relative_to(ROOT), flush=True)

if __name__ == "__main__":
    asyncio.run(go(sys.argv[1:] or [group for group in GROUPS if group != "reenvio"]))

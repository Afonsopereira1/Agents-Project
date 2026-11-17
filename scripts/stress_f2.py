"""Bloco F2: ocorrências em paralelo, rajada e mensagens inválidas (usa extra_initiators e faults.flood).

Um caçador na célula de cada sensor iniciador; fontes sem ruído (alcance 1) e
política sem corroboração, para que cada iniciador trate só a sua ameaça e a
única variável seja a disputa pelos três recursos. Sementes 1000+i, 10 execuções.
Cada grupo grava results/stress/<grupo>.csv; tempo_real_s depende da máquina.
Uso, a partir da raiz: PYTHONPATH=src python scripts/stress_f2.py [grupo ...]
Grupos: paralelo (1, 2, 4 e 8 ocorrências) invalidas escala (C4 mínimo + C1)
        prazo (prazo fixo contra prazo dinâmico, max_receive_timeout) teto (vários tetos)
        fila (queue_rounds) silencio (silent_invalid) espera (fila com ameaças que duram pouco)
        prioridade (queue_priority)
"""
import asyncio, collections, copy, csv, logging, sys, time
from pathlib import Path

from isia.domain.models import Position
from isia.evaluation.collector import load_scenario
from isia.reasoning.reputation import ReputationBook
from isia.simulation.runner import run_mvp

from stress_f1 import double_bookings, mean

logging.disable(logging.CRITICAL)  # milhares de avisos de mensagens rejeitadas
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "stress"
base = load_scenario(ROOT / "config" / "scenarios" / "A.json")
THREAT = base["episodes"][0]["events"][0]
REPS = 10
# Sensores a 2 ou mais células uns dos outros: com alcance 1, cada um só vê a sua ameaça.
EXTRA = {f"sensor-{i + 3}": Position(x, y) for i, (x, y) in enumerate(
    ((6, 2), (0, 5), (2, 5), (4, 5), (6, 5), (1, 7), (4, 7)))}

def setup(count):
    extra = dict(list(EXTRA.items())[:count - 1])
    noiseless = {"kind": "acoustic", "detection_range": 1.0}
    sources = {"sensor-1": noiseless, "sensor-2": {"kind": "visual", "detection_range": 0.0},
               **{key: noiseless for key in extra}}
    settings = copy.deepcopy(base["response_settings"])
    settings["policy"].update(patrol_threshold=0.01, severe_patrol_threshold=0.01)  # como no_corroboration
    settings["sources"].update({key: {"modality": "acoustic", "correlation_group": f"local_{key}"}
                                for key in extra})
    events = [{**THREAT, "event_id": f"threat-{key}", "position": {"x": p.x, "y": p.y}}
              for key, p in {"sensor-1": Position(2, 2), **extra}.items()]
    return extra, sources, settings, events

async def run(count, rep, flood=0, faults=None, duration=None, severities=None, **options):
    extra, sources, settings, events = setup(count)
    if severities is not None:
        settings["severity_by_source"] = severities
    if duration is not None:
        events = [{**event, "duration": duration} for event in events]
    return await run_mvp(
        response_settings=settings, reputation=ReputationBook(**settings["reputation"]),
        corroborate=False, extra_initiators=extra, faults=faults or ({"flood": flood} if flood else None), **options,
        max_seconds=120.0, scenario={"run_id": f"f2-{rep}", "seed": 1000 + rep, "sources": sources,
                                     "events": events, "resources": base["resources"]})

def incidents(report):
    """Uma linha por iniciador: estado, motivo, confirmação pela patrulha e instante do fecho."""
    closed_at = {e.get("initiator", "sensor-1"): e["time"] for e in report["timeline"]
                 if e["event"] == "INCIDENT_CLOSED"}
    views = {"sensor-1": report, **report["extra_initiators"]}
    return [{"status": v["incident_status"], "reason": v["reason"], "closed_at": closed_at.get(key),
             "confirmed": any(r["payload"]["task"] == "verify_incident" and r["payload"]["outcome"] == "confirmed"
                              for r in v["results"])} for key, v in views.items()]

async def paralelo():
    fields = ["ocorrencias", "runs", "total", "confirmadas_patrulha", "fechadas_com_guarda", "unresolved",
              "motivos", "status_reservation_failed", "cfp_ronda_2", "recusas_REJECT", "duplas_reservas",
              "t_fecho_sim_fechadas_mean", "msgs_mean", "tempo_real_s"]
    out = []
    for count in (1, 2, 4, 8):
        rows, msgs, failed, round2, rejects, doubles, t0 = [], [], 0, 0, 0, 0, time.monotonic()
        for rep in range(REPS):
            report = await run(count, rep)
            rows += incidents(report)
            bodies = [(m["sender"], m["body"]) for m in report["messages"]]
            msgs.append(len(bodies))
            failed += sum(b["message_type"] == "STATUS" and b["payload"]["status"] != "reserved" for _, b in bodies)
            round2 += sum(b["message_type"] == "CFP" and b["payload"].get("round_number", 1) > 1 for _, b in bodies)
            rejects += sum(b["message_type"] == "REJECT" and not s.startswith("sensor") for s, b in bodies)
            doubles += double_bookings(report)
        out.append({"ocorrencias": count, "runs": REPS, "total": len(rows),
                    "confirmadas_patrulha": sum(r["confirmed"] for r in rows),
                    "fechadas_com_guarda": sum(r["status"] == "closed" for r in rows),
                    "unresolved": sum(r["status"] == "unresolved" for r in rows),
                    "motivos": " ".join(f"{k}={v}" for k, v in collections.Counter(r["reason"] for r in rows).items()),
                    "status_reservation_failed": failed, "cfp_ronda_2": round2, "recusas_REJECT": rejects,
                    "duplas_reservas": doubles, "t_fecho_sim_fechadas_mean": mean(r["closed_at"] for r in rows if r["status"] == "closed"),
                    "msgs_mean": mean(msgs), "tempo_real_s": round(time.monotonic() - t0, 1)})
        print(out[-1], flush=True)
    return fields, out

async def invalidas():
    fields = ["flood_por_mensagem", "runs", "lixo_injetado_mean", "resultado_igual_a_referencia", "excecoes",
              "estados", "msgs_mean", "respostas_a_lixo_mean", "tempo_real_s"]
    out, reference = [], {}
    for flood in (0, 10, 100, 300, 1000):
        same, errors, junk, msgs, replies, states, t0 = 0, 0, [], [], [], collections.Counter(), time.monotonic()
        for rep in range(REPS):
            try:
                report = await run(1, rep, flood)
            except Exception as error:  # um agente que termina com exceção faz o runner levantar
                errors += 1; states[type(error).__name__] += 1
                continue
            result = (report["incident_status"], report["reason"],
                      [r["payload"]["outcome"] for r in report["results"]])
            reference.setdefault(rep, result)
            same += result == reference[rep]
            states[f"{result[0]}/{result[1]}"] += 1
            junk.append(sum((2 if e["type"] == "CFP" else 3) * flood
                            for e in report["fault_log"] if e["fault"] == "flood"))
            msgs.append(len(report["messages"]))
            replies.append(sum("junk-" in str(m["body"]) for m in report["messages"]))
        out.append({"flood_por_mensagem": flood, "runs": REPS, "lixo_injetado_mean": mean(junk),
                    "resultado_igual_a_referencia": same, "excecoes": errors,
                    "estados": " ".join(f"{k}={v}" for k, v in states.items()), "msgs_mean": mean(msgs),
                    "respostas_a_lixo_mean": mean(replies), "tempo_real_s": round(time.monotonic() - t0, 1)})
        print(out[-1], flush=True)
    return fields, out

async def escala():
    """Mensagens em função do número de patrulhas N, sem limite (antes) e com CFP só às K=2 mais próximas (C1)."""
    fields = ["patrulhas", "cfp_limit", "runs", "fechadas_com_guarda", "msgs_mean", "cfp_mean", "proposal_mean",
              "reject_mean", "t_fecho_sim_fechadas_mean", "primeira_patrulha", "tempo_real_s"]
    far = [Position(x, y) for x in (7, 6, 5) for y in range(8)]  # bases longe do alvo (2,2)
    out = []
    for patrols in (2, 4, 8, 16):
        for limit in (None, 2):
            extra = {f"drone-{i + 2}": far[i] for i in range(patrols - 2)}
            reports, t0 = [], time.monotonic()
            for rep in range(REPS):
                reports.append(await run(1, rep, extra_patrols=extra, cfp_limit=limit))
            kinds = [collections.Counter(m["body"]["message_type"] for m in r["messages"]) for r in reports]
            rows = [row for r in reports for row in incidents(r)]
            first = collections.Counter(next((e["resource_id"] for e in r["timeline"] if e["event"] == "reserved"
                                              and "position" in e), None) for r in reports)
            out.append({"patrulhas": patrols, "cfp_limit": limit or "sem limite", "runs": REPS,
                        "fechadas_com_guarda": sum(r["status"] == "closed" for r in rows),
                        "msgs_mean": mean(len(r["messages"]) for r in reports),
                        "cfp_mean": mean(k["CFP"] for k in kinds), "proposal_mean": mean(k["PROPOSAL"] for k in kinds),
                        "reject_mean": mean(k["REJECT"] for k in kinds),
                        "t_fecho_sim_fechadas_mean": mean(r["closed_at"] for r in rows if r["status"] == "closed"),
                        "primeira_patrulha": " ".join(f"{k}={v}" for k, v in first.items()),
                        "tempo_real_s": round(time.monotonic() - t0, 1)})
            print(out[-1], flush=True)
    return fields, out

async def prazo():
    """Antes e depois do prazo dinâmico: as mesmas falhas com o prazo fixo (0,5 s) e com teto de 2,0 s."""
    fields = ["caso", "prazo", "runs", "fechadas", "estados", "tempo_real_por_execucao_s"]
    off = lambda *names: {"unavailable_agents": [f"{n}-mvp" for n in names]}
    cases = [("sem falhas", None),
             *((f"{kind} delay={d}s", {"delay": {kind: d}})
               for kind, delays in (("PROPOSAL", (0.4, 0.6, 1.5, 2.5)), ("STATUS", (0.6, 1.5, 2.5))) for d in delays),
             ("-drone", off("drone")), ("-drone -vehicle", off("drone", "vehicle")), ("-ranger", off("ranger")),
             *((f"flood={n}", {"flood": n}) for n in (1000, 2000, 5000, 8000))]
    out = []
    for name, faults in cases:
        for label, ceiling in (("fixo 0.5 s", None), ("dinâmico 0.5 a 2.0 s", 2.0)):
            states, t0 = collections.Counter(), time.monotonic()
            for rep in range(REPS):
                try:
                    report = await run(1, rep, faults=faults, max_receive_timeout=ceiling)
                    states[f"{report['incident_status']}/{report['reason']}"] += 1
                except Exception as error:
                    states[type(error).__name__] += 1
            out.append({"caso": name, "prazo": label, "runs": REPS, "fechadas": states["closed/confirmed"],
                        "estados": " ".join(f"{k}={v}" for k, v in states.items()),
                        "tempo_real_por_execucao_s": round((time.monotonic() - t0) / REPS, 2)})
            print(out[-1], flush=True)
    return fields, out

async def teto():
    """Sensibilidade do teto do prazo dinâmico: atraso tolerado contra tempo perdido quando ninguém responde."""
    fields = ["caso", "teto_s", "runs", "fechadas", "estados", "tempo_real_por_execucao_s"]
    cases = [*((f"PROPOSAL delay={d}s", {"delay": {"PROPOSAL": d}}) for d in (0.6, 1.5, 3.0)),
             ("-drone -vehicle", {"unavailable_agents": ["drone-mvp", "vehicle-mvp"]})]
    out, reps = [], 5  # sem perdas aleatórias, as execuções de cada célula são iguais
    for name, faults in cases:
        for ceiling in (0.5, 1.0, 2.0, 4.0):
            states, t0 = collections.Counter(), time.monotonic()
            for rep in range(reps):
                report = await run(1, rep, faults=faults, max_receive_timeout=ceiling)
                states[f"{report['incident_status']}/{report['reason']}"] += 1
            out.append({"caso": name, "teto_s": ceiling, "runs": reps, "fechadas": states["closed/confirmed"],
                        "estados": " ".join(f"{k}={v}" for k, v in states.items()),
                        "tempo_real_por_execucao_s": round((time.monotonic() - t0) / reps, 2)})
            print(out[-1], flush=True)
    return fields, out

async def fila():
    """Antes e depois da fila: 2, 4 e 8 ocorrências com queue_rounds a 0 e a 60."""
    fields = ["ocorrencias", "queue_rounds", "runs", "total", "fechadas_com_guarda", "unresolved", "motivos",
              "t_ultimo_fecho_sim_mean", "msgs_mean", "cfp_mean", "duplas_reservas", "tempo_real_por_execucao_s"]
    out = []
    for count in (2, 4, 8):
        for rounds in (0, 60):
            rows, last, msgs, cfps, doubles, t0 = [], [], [], [], 0, time.monotonic()
            for rep in range(REPS):
                report = await run(count, rep, queue_rounds=rounds)
                one = incidents(report)
                rows += one
                last.append(max((r["closed_at"] for r in one if r["status"] == "closed"), default=None))
                msgs.append(len(report["messages"]))
                cfps.append(sum(m["body"]["message_type"] == "CFP" for m in report["messages"]))
                doubles += double_bookings(report)
            out.append({"ocorrencias": count, "queue_rounds": rounds, "runs": REPS, "total": len(rows),
                        "fechadas_com_guarda": sum(r["status"] == "closed" for r in rows),
                        "unresolved": sum(r["status"] == "unresolved" for r in rows),
                        "motivos": " ".join(f"{k}={v}" for k, v in collections.Counter(r["reason"] for r in rows).items()),
                        "t_ultimo_fecho_sim_mean": mean(last), "msgs_mean": mean(msgs), "cfp_mean": mean(cfps),
                        "duplas_reservas": doubles,
                        "tempo_real_por_execucao_s": round((time.monotonic() - t0) / REPS, 2)})
            print(out[-1], flush=True)
    return fields, out

async def espera():
    """Problemas de esperar na fila: 8 ocorrências, queue_rounds=60, ameaças que duram 1000, 60 e 30 s."""
    fields = ["duracao_ameaca_s", "runs", "total", "fechadas_confirmadas", "patrulha_em_vao", "guarda_apos_fim_da_ameaca",
              "rondas_ao_guarda_mean", "rondas_ao_guarda_max", "msgs_mean"]
    out = []
    for duration in (1000.0, 60.0, 30.0):
        confirmed, late, after, rounds, msgs = 0, 0, 0, [], []
        for rep in range(REPS):
            report = await run(8, rep, duration=duration, queue_rounds=60)
            views = [report, *report["extra_initiators"].values()]
            confirmed += sum(v["incident_status"] == "closed" and v["reason"] == "confirmed" for v in views)
            results = [r["payload"] for v in views for r in v["results"]]
            # Em vão: a patrulha chegou ao alvo e a ameaça já lá não estava.
            late += sum(r["task"] == "verify_incident" and r["outcome"] == "not_confirmed" for r in results)
            # A intervenção do guarda é sempre "confirmed" no simulador; contar as que acabam depois do fim da ameaça.
            after += sum(r["task"] == "respond_incident" and r["completed_at"] > duration for r in results)
            last = collections.Counter()
            for m in report["messages"]:
                if m["body"]["message_type"] == "CFP" and m["to"].startswith("ranger"):
                    last[m["sender"]] = max(last[m["sender"]], m["body"]["payload"]["round_number"])
            rounds += last.values(); msgs.append(len(report["messages"]))
        out.append({"duracao_ameaca_s": duration, "runs": REPS, "total": 8 * REPS, "fechadas_confirmadas": confirmed,
                    "patrulha_em_vao": late, "guarda_apos_fim_da_ameaca": after,
                    "rondas_ao_guarda_mean": mean(rounds), "rondas_ao_guarda_max": max(rounds, default=0),
                    "msgs_mean": mean(msgs)})
        print(out[-1], flush=True)
    return fields, out

async def prioridade():
    """Antes e depois da fila ordenada: 8 ocorrências (2 graves, 3 médias, 3 leves) com queue_rounds=60."""
    fields = ["fila", "gravidade", "ocorrencias", "fechadas", "t_fecho_sim_mean", "t_fecho_sim_max",
              "msgs_mean", "duplas_reservas"]
    names = {0.2: "leve", 0.5: "média", 0.9: "grave"}  # limiar grave da política: 0,8; média a partir de 0,4
    levels = dict(zip(("sensor-1", *EXTRA), (0.2, 0.2, 0.2, 0.5, 0.5, 0.5, 0.9, 0.9)))
    out = []
    for label, order in (("sem ordem", False), ("por gravidade", True)):
        times, total, msgs, doubles = collections.defaultdict(list), collections.Counter(), [], 0
        for rep in range(REPS):
            report = await run(8, rep, severities=levels, queue_rounds=60, queue_priority=order)
            closed_at = {e.get("initiator", "sensor-1"): e["time"] for e in report["timeline"]
                         if e["event"] == "INCIDENT_CLOSED"}
            for key, view in {"sensor-1": report, **report["extra_initiators"]}.items():
                total[names[levels[key]]] += 1
                if view["incident_status"] == "closed":
                    times[names[levels[key]]].append(closed_at[key])
            msgs.append(len(report["messages"])); doubles += double_bookings(report)
        for level in ("grave", "média", "leve"):
            out.append({"fila": label, "gravidade": level, "ocorrencias": total[level], "fechadas": len(times[level]),
                        "t_fecho_sim_mean": mean(times[level]), "t_fecho_sim_max": max(times[level], default=None),
                        "msgs_mean": mean(msgs), "duplas_reservas": doubles})
            print(out[-1], flush=True)
    return fields, out

async def silencio():
    """Antes e depois de silent_invalid: quantas respostas os agentes dão às mensagens inválidas."""
    fields = ["flood_por_mensagem", "silent_invalid", "runs", "fechadas", "lixo_injetado_mean",
              "respostas_a_lixo_mean", "respostas_por_remetente", "msgs_mean"]
    out = []
    for flood in (10, 100, 300):
        for silent in (False, True):
            closed, junk, replies, msgs, senders = 0, [], [], [], collections.Counter()
            for rep in range(REPS):
                report = await run(1, rep, flood, silent_invalid=silent)
                closed += report["incident_status"] == "closed"
                junk.append(sum((2 if e["type"] == "CFP" else 3) * flood
                                for e in report["fault_log"] if e["fault"] == "flood"))
                answered = [m["sender"].split("-mvp")[0] for m in report["messages"] if "junk-" in str(m["body"])]
                replies.append(len(answered)); senders.update(answered); msgs.append(len(report["messages"]))
            out.append({"flood_por_mensagem": flood, "silent_invalid": silent, "runs": REPS, "fechadas": closed,
                        "lixo_injetado_mean": mean(junk), "respostas_a_lixo_mean": mean(replies),
                        "respostas_por_remetente": " ".join(f"{k}={v // REPS}" for k, v in senders.items()),
                        "msgs_mean": mean(msgs)})
            print(out[-1], flush=True)
    return fields, out

async def go(groups):
    OUT.mkdir(parents=True, exist_ok=True)
    for group in groups:
        fields, out = await globals()[group]()
        path = OUT / f"{group}.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fields, lineterminator="\n"); w.writeheader(); w.writerows(out)
        print("gravado:", path.relative_to(ROOT), flush=True)

if __name__ == "__main__":
    asyncio.run(go(sys.argv[1:] or ["paralelo", "invalidas", "escala", "prazo", "teto", "fila", "silencio", "espera", "prioridade"]))

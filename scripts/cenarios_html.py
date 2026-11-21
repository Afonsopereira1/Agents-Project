"""Embutir os cenários e uma execução gravada de cada um em deliverables/cenarios.html.

Só lê configurações e relatórios; não corre agentes. Substitui o bloco de dados da página.
Os relatórios de A, B, C e E vêm de results/*/runs/, que não são versionados: é preciso
tê-los localmente (collector) para regenerar a página.
Uso, a partir da raiz:  python scripts/cenarios_html.py
"""
import json
import re
from math import hypot
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "deliverables/cenarios.html"
# cenário: (configuração, relatório para o replay, porque foi escolhido)
SCENARIOS = {
    "A": ("config/scenarios/A.json", "results/experiments/runs/A/full/A-full-000-threat.json",
          "Caso típico: corroborada, o veículo verifica e o guarda fecha aos 12 s."),
    "B": ("config/scenarios/B.json", "results/experiments/runs/B/full/B-full-002-thunder+tourist.json",
          "Falso alarme: trovão e turista geram dois sinais compatíveis e a patrulha não encontra nada."),
    "C": ("config/scenarios/C.json", "results/experiments/runs/C/full/C-full-007-threat.json",
          "Uma mensagem perdida: o guarda intervém, mas o resultado nunca chega ao sensor."),
    "D": ("config/scenarios/demo/D.json", "results/demo/d.json",
          "Seis ocorrências em paralelo; a ameaça de 15 s expira antes de ser atendida."),
    "E": ("config/scenarios/demo/E.json", "results/scenario-e/runs/E/full/E-full-005-wide.json",
          "Dezasseis ocorrências para seis recursos; duas leves ficam sem guarda com autonomia."),
}
MVP_SENSORS = {"sensor-1": {"x": 2, "y": 2}, "sensor-2": {"x": 4, "y": 2}}
STATES = {"verifying", "assessing", "allocating", "responding", "closed", "expired", "unresolved"}
DECISION = {"request_mobile_verification": "pede verificação por patrulha", "observe": "continua só a observar",
            "request_rangers": "pede guardas"}
REASON = {"confirmed": "ameaça confirmada, guarda no local", "not_confirmed": "nada encontrado no local",
          "insufficient_corroboration": "sem corroboração suficiente", "threat_expired": "passou o prazo de validade",
          "no_eligible_proposals": "nenhum recurso elegível", "mission_result_unknown": "o resultado da missão nunca chegou",
          "confirmation_unknown": "a confirmação nunca chegou", "no_alert": "o sensor não deu alerta"}
OUTCOME = {"confirmed": "confirma a ameaça", "not_confirmed": "não encontra nada"}


def short(jid):
    """Encurtar um JID para o ID do recurso ou do sensor.

    Ex.: ``drone-2-mvp@localhost`` dá ``drone-2``; o sensor base (``sensor``, ``sensor-peer``)
    fica com o seu ID (``sensor-1``, ``sensor-2``).

    Args:
        jid (str): JID XMPP do agente.

    Returns:
        str: ID curto usado na página.
    """
    name = jid.split("-mvp")[0]
    return {"sensor": "sensor-1", "sensor-peer": "sensor-2"}.get(name, name)


def replay(config, report, note):
    """Reduzir um relatório do run_mvp ao que a página anima: trajetos, estados, registo e mensagens.

    Args:
        config (dict): Configuração do cenário (``episodes``, ``response_settings`` e, se houver,
            ``world``).
        report (dict): Relatório gravado: a saída do ``run_mvp`` ou um ficheiro do coletor (com as
            chaves ``report`` e ``metrics``).
        note (str): Porque é que esta execução foi escolhida, mostrado na página.

    Returns:
        dict: Dados do replay: ``run`` (id), ``ep`` (índice do episódio), ``note``, ``tmax`` (s),
            ``res`` (trajetos por recurso: ``[t, x, y, energia]``), ``inc`` (ocorrências com
            estados, alvo, duração e severidade), ``log`` (``[t, texto]`` ordenado) e ``msgs``
            (``[t, total acumulado de mensagens]``).
    """
    metrics, report = report.get("metrics", {}), report.get("report", report)
    timeline, world, settings = report["timeline"], config.get("world", {}), config["response_settings"]
    episode = next(e for e in config["episodes"] if e["label"] == metrics["episode"])
    sensors = {**MVP_SENSORS, **world.get("sensors", {}), **world.get("initiators", {})}
    tracks = {r["resource_id"]: [[0.0, r["position"]["x"], r["position"]["y"], r["autonomy_percent"]]]
              for r in report["initial_resources"]}
    incidents = {key: {"id": key, "st": []} for key in ["sensor-1", *world.get("initiators", {})]}
    log = []
    for e in timeline:
        t, kind, who = e["time"], e["event"], e.get("initiator", "sensor-1")
        if "position" in e and "resource_id" in e:
            point = [t, e["position"]["x"], e["position"]["y"], e["energy"]]
            if tracks[e["resource_id"]][-1][1:] != point[1:]:
                tracks[e["resource_id"]].append(point)
            if kind == "MISSION_RESULT":
                log.append([t, f"{e['resource_id']} inspeciona ({point[1]}, {point[2]}) e {OUTCOME.get(e['outcome'], e['outcome'])}"])
            continue
        if "resource_id" in e:
            continue  # cópia do lado do sensor: o registo usa a do recurso
        if kind == "CFP":
            incidents[who].setdefault("target", e["payload"]["target"])
        elif kind == "ALERT":
            log.append([t, f"{who} deteta um sinal e abre uma ocorrência"])
        elif kind == "corroboration":
            log.append([t, f"{who} {DECISION.get(e['decision']['decision'], e['decision']['decision'])}"])
        elif kind == "ACCEPT":
            task = "intervir" if e["mission_id"].endswith("-response") else "verificar"
            log.append([t, f"{who} entrega a {short(e['recipient'])} a missão de {task}"])
        elif kind == "INCIDENT_CLOSED":
            incidents[who].update(reason=e["reason"], why=REASON.get(e["reason"], e["reason"]))
            log.append([t, f"{who} termina a ocorrência: {REASON.get(e['reason'], e['reason'])}"])
        elif kind in STATES and "recipient" not in e:
            incidents[who]["st"].append([t, kind])
    sent = {m["body"]["message_id"]: m for m in report["messages"]}
    for fault in report["fault_log"]:
        if fault["fault"] == "lost" and fault["message_id"] in sent:
            m = sent[fault["message_id"]]
            log.append([m["body"]["created_at"], f"PERDIDA: {fault['type']} de {short(m['sender'])} para {short(m['to'])}"])
    for key, inc in incidents.items():
        here = sensors[key]
        event = min(episode["events"], key=lambda ev: hypot(ev["position"]["x"] - here["x"], ev["position"]["y"] - here["y"]),
                    default=None)
        inc.setdefault("target", event["position"] if event else here)
        inc["dur"] = event["duration"] if event else None
        inc["sev"] = settings.get("severity_by_source", {}).get(key, settings["severity"])
        if not inc["st"]:
            inc.update(reason="no_alert", why=REASON["no_alert"])
    times = sorted(m["body"]["created_at"] for m in report["messages"])
    return {"run": report["run_id"], "ep": config["episodes"].index(episode), "note": note,
            "tmax": max(e["time"] for e in timeline), "res": tracks, "inc": list(incidents.values()),
            # No mesmo instante, o fecho da ocorrência fica depois da inspeção que o causou.
            "log": sorted(log, key=lambda line: (line[0], " termina a ocorrência" in line[1])),
            "msgs": [[t, i + 1] for i, t in enumerate(times) if i + 1 == len(times) or times[i + 1] != t]}


def main():
    """Gerar o replay de cada cenário e substituir o bloco de dados de ``cenarios.html``.

    Raises:
        AssertionError: Se os recursos ou alvos de um replay não baterem com o cenário, ou se a
            página não tiver exatamente um bloco ``<script id="data">``.
    """
    data = {}
    for key, (config_path, report_path, note) in SCENARIOS.items():
        config = json.loads((ROOT / config_path).read_text(encoding="utf-8"))
        report = json.loads((ROOT / report_path).read_text(encoding="utf-8"))
        data[key] = {**config, "replay": replay(config, report, note)}
        r = data[key]["replay"]
        # Self-check: os recursos do relatório são os do cenário e toda a ocorrência tem alvo no mapa.
        extra = config.get("world", {})
        assert set(r["res"]) == {"drone", "vehicle", "ranger", *extra.get("patrols", {}), *extra.get("rangers", {})}, key
        assert all(0 <= i["target"]["x"] < extra.get("width", 8) and 0 <= i["target"]["y"] < extra.get("height", 8) for i in r["inc"]), key
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page, count = re.subn(r'(<script type="application/json" id="data">).*?(</script>)',
                          lambda m: m.group(1) + blob + m.group(2), PAGE.read_text(encoding="utf-8"), flags=re.S)
    assert count == 1, "bloco de dados não encontrado na página"
    PAGE.write_text(page, encoding="utf-8")
    print(f"{PAGE.relative_to(ROOT)}: {len(blob) // 1024} kB de dados, "
          + ", ".join(f"{k} {v['replay']['run']} ({v['replay']['tmax']:g} s)" for k, v in data.items()))


if __name__ == "__main__":
    main()

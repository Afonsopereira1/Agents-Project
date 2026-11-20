"""Sugestões da escalabilidade situacional: procurar o ponto a partir do qual mais já não ajuda, e testá-lo.

Quatro grupos, cada um varre um só parâmetro:
  guardas    cenário E (16 ameaças) com 2, 3 e 4 guardas
  reenvios   perda de 10, 20 e 30 % com 0 a 4 reenvios por pedido (cenário A, 20 sementes)
  distancia  ameaça de 15 s e o guarda a 5, 6, 7, 8 e 9 células do alvo (fontes sem ruído)
  cobertura  ameaça em (7,0), fora do alcance do sensor-1, sem e com um sensor iniciador que a alcança
Grava results/stress/sugestoes.csv. Uso, a partir da raiz:
  PYTHONPATH=src python scripts/sugestoes.py [grupo ...]
"""
import asyncio, copy, csv, sys
from pathlib import Path

from isia.domain.models import Position
from isia.evaluation.collector import load_scenario, run_scenario
from isia.reasoning.reputation import ReputationBook
from isia.simulation.runner import PUBLISHED_CONDITIONS, run_mvp

from stress_f1 import case, mean
from stress_f2 import incidents

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "stress" / "sugestoes.csv"
A = load_scenario(ROOT / "config" / "scenarios" / "A.json")
E = load_scenario(ROOT / "config" / "scenarios" / "demo" / "E.json")
THREAT = A["episodes"][0]["events"][0]
FIELDS = ["grupo", "valor", "runs", "ameacas", "com_alerta", "chegam_ao_guarda", "unresolved",
          "t_fecho_sim_mean", "msgs_mean"]


def row(grupo, valor, reports):
    """Agregar relatórios numa linha do CSV, contando uma ocorrência por iniciador.

    Args:
        grupo (str): Nome do grupo, na coluna ``grupo``.
        valor (str): Descrição do caso, na coluna ``valor``.
        reports (list[dict]): Relatórios das execuções do caso (saída de ``run_mvp``).

    Returns:
        dict: Linha com as colunas de ``FIELDS``; ``t_fecho_sim_mean`` é a média, em s
            simulados, das ocorrências fechadas com ameaça confirmada.
    """
    views = [v for r in reports for v in incidents(r)]
    done = [v for v in views if v["status"] == "closed" and v["reason"] == "confirmed"]
    return {"grupo": grupo, "valor": valor, "runs": len(reports),
            "ameacas": sum(e["is_threat"] for r in reports for e in r["ground_truth"]["events"]),
            "com_alerta": sum(v["status"] is not None for v in views), "chegam_ao_guarda": len(done),
            "unresolved": sum(v["status"] == "unresolved" for v in views),
            "t_fecho_sim_mean": mean(v["closed_at"] for v in done),
            "msgs_mean": mean(len(r["messages"]) for r in reports)}


async def guardas():
    """Testar o cenário E com 2, 3 e 4 guardas (acrescenta ``ranger-3`` e ``ranger-4``).

    Returns:
        list[dict]: Uma linha por caso, com as colunas de ``FIELDS``: ``grupo``, ``valor``,
            ``runs``, ``ameacas``, ``com_alerta``, ``chegam_ao_guarda``, ``unresolved``,
            ``t_fecho_sim_mean`` (média, por execução, do instante do último fecho, em s
            simulados) e ``msgs_mean``.
    """
    extra = {"ranger-3": {"x": 8, "y": 3}, "ranger-4": {"x": 8, "y": 9}}
    out = []
    for n in (2, 3, 4):
        config = copy.deepcopy(E)
        config["world"]["rangers"].update(dict(list(extra.items())[:n - 2]))
        rows = await run_scenario(config, "full")
        out.append({"grupo": "guardas", "valor": f"{n} guardas para 16 ameaças", "runs": len(rows),
                    "ameacas": 16 * len(rows), "com_alerta": sum(r["incidents"] for r in rows),
                    # Em E todas as fechadas são confirmadas pelo guarda (ver scripts/scenario_e.py).
                    "chegam_ao_guarda": sum(r["incidents_closed"] for r in rows),
                    "unresolved": sum(r["incidents_unresolved"] for r in rows),
                    "t_fecho_sim_mean": mean(r["last_close_time"] for r in rows),
                    "msgs_mean": mean(r["messages_sent"] for r in rows)})
    return out


async def reenvios():
    """Testar perdas de 10, 20 e 30 % com 0 a 4 reenvios; 20 execuções por caso no cenário A.

    Returns:
        list[dict]: Uma linha por caso, com as colunas de ``FIELDS``: ``grupo``, ``valor``,
            ``runs``, ``ameacas``, ``com_alerta``, ``chegam_ao_guarda``, ``unresolved``,
            ``t_fecho_sim_mean`` (sempre ``None``) e ``msgs_mean``.
    """
    out = []
    for loss in (0.1, 0.2, 0.3):
        for n in range(5):
            r = await case(f"perda {loss:.0%}, {n} reenvios", A["resources"], {"loss": loss}, 20,
                           {"retransmit": n, "max_seconds": None})
            out.append({"grupo": "reenvios", "valor": r["caso"], "runs": r["runs"], "ameacas": r["runs"],
                        "com_alerta": r["alerta"], "chegam_ao_guarda": r["closed"], "unresolved": r["unresolved"],
                        "t_fecho_sim_mean": None, "msgs_mean": r["msgs_mean"]})
    return out


async def simple(run_id, events, resources, sources, settings, **options):
    """Correr uma execução com reputação nova; a semente é 1000 + o sufixo do ``run_id``.

    Args:
        run_id (str): Id da execução, terminado em ``-N`` (ex.: ``dist-3``).
        events (list[dict]): Eventos do episódio.
        resources (dict): Overrides dos recursos.
        sources (dict): Fontes (tipo e alcance) por ID de sensor.
        settings (dict): ``response_settings`` do cenário, com ``reputation``.
        **options: Argumentos extra do ``run_mvp`` (ex.: ``extra_initiators``); sobrepõem-se às
            condições publicadas.

    Returns:
        dict: Relatório da execução devolvido pelo ``run_mvp``.
    """
    return await run_mvp(response_settings=settings, reputation=ReputationBook(**settings["reputation"]),
                         **{**PUBLISHED_CONDITIONS, **options}, max_seconds=30.0,
                         scenario={"run_id": run_id, "seed": 1000 + int(run_id.rsplit("-", 1)[1]),
                                   "sources": sources, "events": events, "resources": resources})


async def distancia():
    """Testar a distância do guarda até ao alvo, de 5 a 9 células, com uma ameaça de 15 s.

    O veículo verifica aos 6 s, o guarda sai depois e demora distância + 1 s. Fontes sem
    ruído; 5 execuções por caso.

    Returns:
        list[dict]: Uma linha por caso, com as colunas de ``FIELDS``: ``grupo``, ``valor``,
            ``runs``, ``ameacas``, ``com_alerta``, ``chegam_ao_guarda``, ``unresolved``,
            ``t_fecho_sim_mean`` e ``msgs_mean``.
    """
    sources = {"sensor-1": {"kind": "acoustic", "detection_range": 5.0}, "sensor-2": {"kind": "visual", "detection_range": 5.0}}
    out = []
    for cells, (x, y) in ((5, (5, 5)), (6, (6, 5)), (7, (7, 5)), (8, (7, 6)), (9, (7, 7))):
        reports = [await simple(f"dist-{rep}", [{**THREAT, "duration": 15.0}],
                                {"drone": {"load": 0.5}, "ranger": {"position": {"x": x, "y": y}}},
                                sources, copy.deepcopy(A["response_settings"])) for rep in range(5)]
        out.append(row("distancia", f"guarda a {cells} células, ameaça de 15 s", reports))
    return out


async def cobertura():
    """Testar uma ameaça em (7,0) sem e com um iniciador adicional em (6,1); 10 execuções cada.

    Returns:
        list[dict]: Uma linha por caso, com as colunas de ``FIELDS``: ``grupo``, ``valor``,
            ``runs``, ``ameacas``, ``com_alerta``, ``chegam_ao_guarda``, ``unresolved``,
            ``t_fecho_sim_mean`` e ``msgs_mean``.
    """
    out = []
    for label, extra in (("só o sensor-1 inicia", None), ("mais um iniciador em (6,1)", {"sensor-3": Position(6, 1)})):
        settings = copy.deepcopy(A["response_settings"])
        sources = dict(A["sources"])
        options = {}
        if extra:
            sources["sensor-3"] = A["sources"]["sensor-1"]
            settings["sources"]["sensor-3"] = {"modality": "acoustic", "correlation_group": "local_sensor-3"}
            options = {"extra_initiators": extra, "extra_informants": {}}  # {}: corrobora com o sensor-2
        reports = [await simple(f"cob-{rep}", [{**THREAT, "position": {"x": 7, "y": 0}}], A["resources"],
                                sources, settings, **options) for rep in range(10)]
        out.append(row("cobertura", f"ameaça em (7,0), {label}", reports))
    return out


GROUPS = {"guardas": guardas, "reenvios": reenvios, "distancia": distancia, "cobertura": cobertura}

if __name__ == "__main__":
    async def go(names):
        """Correr os grupos pedidos e regravar o CSV, mantendo as linhas dos outros.

        Args:
            names (list[str]): Nomes de grupos de ``GROUPS``, pela ordem a correr.
        """
        rows = []
        for name in names:
            for r in await GROUPS[name]():
                print(r, flush=True)
                rows.append(r)
        # Grupos não corridos mantêm as linhas que já estavam no ficheiro.
        kept = [r for r in csv.DictReader(OUT.open(encoding="utf-8")) if r["grupo"] not in names] if OUT.exists() else []
        with OUT.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, FIELDS, lineterminator="\n"); w.writeheader(); w.writerows(kept + rows)
    asyncio.run(go(sys.argv[1:] or list(GROUPS)))

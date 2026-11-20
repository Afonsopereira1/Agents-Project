"""Executar o MVP: transporte local de teste ou agentes ligados a XMPP.

Por onde começar: `run_mvp`, que monta o mundo, cria os agentes, injeta falhas
(`fault_settings`) e devolve o relatório com a timeline."""

import argparse
import asyncio
import json
import os
import random
from contextlib import suppress
from copy import copy, deepcopy

from spade.behaviour import OneShotBehaviour

from isia.agents import sensor as sensor_module
from isia.agents.drone import DroneAgent
from isia.agents.vehicle import VehicleAgent
from isia.agents.ranger import RangerAgent
from isia.agents.incident import IncidentSensorAgent
from isia.agents.informant import InformantAgent
from isia.communication.messages import MessageType, model_from_dict, model_to_dict
from isia.domain.models import Position, ResourceState
from isia.domain.validation import is_finite_number
from isia.reasoning.policy import ResponsePolicy
from isia.reasoning.reputation import ReputationBook, result_from_mission
from isia.simulation.movement import distance
from isia.simulation.world import World
from isia.simulation.scenario import Scenario, Source, Event, event_from_dict


SCENARIO_SEED = 6
MVP_RESOURCE_IDS = frozenset(("drone", "vehicle", "ranger"))
MVP_AGENT_IDS = frozenset(("sensor-mvp", "sensor-peer-mvp", *(
    f"{resource_id}-mvp" for resource_id in MVP_RESOURCE_IDS
)))
FAULT_DEFAULTS = {"seed": 0, "loss": 0.0, "delay": {}, "drop": [], "duplicate": [],
                  "unavailable_agents": [], "occupied_after_proposal": [], "flood": 0}


def fault_settings(faults):
    """Validar a injeção de falhas do transporte local (Etapa 8).

    Args:
        faults (dict | None): Chaves de ``FAULT_DEFAULTS`` a alterar (``seed``, ``loss``,
            ``delay``, ``drop``, ``duplicate``, ``unavailable_agents``,
            ``occupied_after_proposal``, ``flood``); None desliga as falhas.

    Returns:
        dict | None: Cópia independente com as omissões preenchidas, ou None sem falhas.

    Raises:
        ValueError: Se houver chaves desconhecidas, valores fora do intervalo ou nomes de
            mensagens, agentes ou recursos que não existem no MVP.
    """
    if faults is None:
        return None
    if not isinstance(faults, dict) or set(faults) - set(FAULT_DEFAULTS):
        raise ValueError(f"faults aceita apenas {sorted(FAULT_DEFAULTS)}.")
    settings = {**FAULT_DEFAULTS, **faults}
    if type(settings["seed"]) is not int:
        raise ValueError("faults.seed deve ser inteiro.")
    if type(settings["loss"]) not in (int, float) or not 0 <= settings["loss"] <= 1:
        raise ValueError("faults.loss deve estar entre 0 e 1.")
    if not isinstance(settings["delay"], dict) or any(
            type(value) not in (int, float) or not 0 <= value < 60 for value in settings["delay"].values()):
        raise ValueError("faults.delay associa tipos de mensagem a segundos em [0, 60[.")
    if type(settings["flood"]) is not int or settings["flood"] < 0:
        raise ValueError("faults.flood deve ser um inteiro não negativo.")
    for key in ("drop", "duplicate", "unavailable_agents", "occupied_after_proposal"):
        if not isinstance(settings[key], list) or any(not isinstance(v, str) for v in settings[key]):
            raise ValueError(f"faults.{key} deve ser uma lista de nomes.")
    message_types = {kind.value for kind in MessageType}
    for key, supported in (
        ("delay", message_types), ("drop", message_types), ("duplicate", message_types),
        ("unavailable_agents", MVP_AGENT_IDS), ("occupied_after_proposal", MVP_RESOURCE_IDS),
    ):
        if any(value not in supported for value in settings[key]):
            raise ValueError(f"faults.{key} aceita apenas {', '.join(sorted(supported))}.")
    # Os parâmetros fornecidos e os defaults têm o mesmo isolamento por execução.
    return deepcopy(settings)


MVP_RESOURCES = {"drone": Position(0, 2), "vehicle": Position(0, 0), "ranger": Position(5, 5)}
RESOURCE_KEYS = {"position", "autonomy_percent", "load"}
CORROBORATION_DEFAULTS = {"max_distance": 3.0, "max_time_difference": 2.0}
# Prazo fixo, sem fila e com resposta a ACCEPT incoerente: as condições dos resultados publicados
# (Etapa 9, P3, Blocos F1 e G). O coletor e os scripts passam-nas a run_mvp para os reproduzir.
PUBLISHED_CONDITIONS = {"max_receive_timeout": None, "queue_rounds": 0, "silent_invalid": False}


def validate_experimental_settings(*, xmpp=False, corroboration_settings=None,
                                   receive_timeout=None, minimum_autonomy_percent=10.0,
                                   selection_weights=None):
    """Validar o Bloco G antes de criar agentes; devolver os valores efetivos.

    A janela de corroboração usa tempo simulado. ``receive_timeout`` é o prazo
    base em tempo real e não o teto dinâmico opcional do Bloco F.

    Args:
        xmpp (bool): Transporte XMPP; muda o prazo por omissão de 0.5 s para 2.0 s.
        corroboration_settings (dict[str, float] | None): ``max_distance`` (células) e
            ``max_time_difference`` (s simulados); None usa ``CORROBORATION_DEFAULTS``.
        receive_timeout (float | None): Prazo base, em segundos reais; None usa a omissão
            do transporte.
        minimum_autonomy_percent (float): Reserva mínima de energia, em % de 0 a 100.
        selection_weights (dict[str, float] | None): Pesos e escalas de seleção de
            propostas; None mantém as omissões do iniciador.

    Returns:
        tuple[dict[str, float], float, float]: Parâmetros de corroboração, prazo base e
            reserva mínima efetivos.

    Raises:
        ValueError: Se houver chaves desconhecidas, valores negativos ou não finitos, prazo
            não positivo, reserva fora de [0, 100], escala nula ou todos os pesos a zero.
    """
    if corroboration_settings is not None and (
            not isinstance(corroboration_settings, dict)
            or set(corroboration_settings) - set(CORROBORATION_DEFAULTS)):
        raise ValueError(f"corroboration_settings aceita apenas {sorted(CORROBORATION_DEFAULTS)}.")
    corroboration = {**CORROBORATION_DEFAULTS, **(corroboration_settings or {})}
    for name, value in corroboration.items():
        if not is_finite_number(value) or value < 0:
            raise ValueError(f"corroboration_settings.{name} deve ser finito e não negativo.")
    timeout = (2.0 if xmpp else 0.5) if receive_timeout is None else receive_timeout
    if not is_finite_number(timeout) or timeout <= 0:
        raise ValueError("receive_timeout deve ser finito e positivo.")
    if not is_finite_number(minimum_autonomy_percent) or not 0 <= minimum_autonomy_percent <= 100:
        raise ValueError("minimum_autonomy_percent deve estar entre 0 e 100.")
    if selection_weights is not None:
        defaults = {"eta_weight": 1.0, "energy_weight": 1.0, "load_weight": 1.0,
                    "eta_scale_seconds": 60.0, "energy_scale_percent": 100.0, "load_scale": 1.0}
        if not isinstance(selection_weights, dict) or set(selection_weights) - set(defaults):
            raise ValueError(f"selection_weights aceita apenas {sorted(defaults)}.")
        cost = {**defaults, **selection_weights}
        for name, value in cost.items():
            if not is_finite_number(value) or value < 0 or ("scale" in name and value == 0):
                raise ValueError(f"selection_weights.{name} inválido: peso não negativo, escala positiva.")
        if not any(cost[name] > 0 for name in ("eta_weight", "energy_weight", "load_weight")):
            raise ValueError("Pelo menos um peso deve ser positivo.")
    return corroboration, timeout, minimum_autonomy_percent


def scenario_settings(scenario):
    """Montar fontes, eventos e recursos de um cenário da Etapa 9.

    O mapa não é criado aqui: vem de ``map_size`` em ``run_mvp`` (8x8 por omissão).

    Args:
        scenario (dict | None): Cenário com ``run_id``, ``seed``, ``sources``, ``events`` e
            ``resources``; None usa o cenário base do MVP (uma ameaça fixa em (3, 2)).

    Returns:
        tuple: Semente, fontes (``dict[str, Source]``), eventos (``tuple[Event, ...]``),
            opções por recurso (``dict``) e prefixo dos identificadores das observações.

    Raises:
        ValueError: Se faltarem ou sobrarem chaves, o ``run_id`` estiver vazio, a semente
            não for inteira, fontes, eventos ou recursos forem inválidos, ou algum evento
            não começar em t=0.
    """
    if scenario is None:
        return (SCENARIO_SEED, {key: Source("acoustic", 5) for key in ("sensor-1", "sensor-2")},
                (Event("event-mvp", "threat", Position(3, 2), 0, 1000),), {}, "obs")
    if not isinstance(scenario, dict) or set(scenario) != {"run_id", "seed", "sources", "events", "resources"}:
        raise ValueError("scenario exige run_id, seed, sources, events e resources.")
    if not isinstance(scenario["run_id"], str) or not scenario["run_id"].strip():
        raise ValueError("scenario.run_id deve identificar a execução.")
    if type(scenario["seed"]) is not int:
        raise ValueError("scenario.seed deve ser inteiro.")
    resources = scenario["resources"]
    if not isinstance(resources, dict) or set(resources) - set(MVP_RESOURCES) or any(
            not isinstance(v, dict) or set(v) - RESOURCE_KEYS for v in resources.values()):
        raise ValueError(f"scenario.resources aceita {sorted(MVP_RESOURCES)} com {sorted(RESOURCE_KEYS)}.")
    try:
        sources = {key: Source(**value) for key, value in scenario["sources"].items()}
        events = tuple(event_from_dict(item) for item in scenario["events"])
    except (AttributeError, KeyError, TypeError) as error:
        raise ValueError("Fontes ou eventos do cenário inválidos.") from error
    if any(event.starts_at != 0 for event in events):
        # O sensor só lê o feed em t=0 (janela única); um evento posterior seria um FN falso.
        raise ValueError("Nesta janela única os eventos têm de começar em t=0.")
    return scenario["seed"], sources, events, resources, f"{scenario['run_id']}-obs"


async def run_mvp(*, xmpp=False, password="local-demo", inspection_outcomes=None,
                  interrupt_resource=None, max_seconds=None,
                  response_settings=None, reputation=None, faults=None,
                  scenario=None, corroborate=True, selection_weights=None, run_id=None,
                  extra_initiators=None, extra_patrols=None, cfp_limit=None, max_receive_timeout=2.0,
                  queue_rounds=60, silent_invalid=True, queue_priority=False,
                  corroboration_settings=None, receive_timeout=None, minimum_autonomy_percent=10.0,
                  extra_rangers=None, extra_informants=None, map_size=(8, 8), sensor_positions=None,
                  expire_unseen=False, queue_until_free=False, chain_missions=False, retransmit=0,
                  alert_distance=None):
    """Correr uma execução do MVP e devolver o relatório.

    O runner só fornece ambiente, relógio e transporte; os agentes decidem. O transporte
    local executa os mesmos comportamentos e contratos SPADE, mas não demonstra entrega
    pela rede XMPP. ``max_receive_timeout``, ``queue_rounds`` e ``silent_invalid`` estão
    ligados por omissão desde 18-11-2026; ``PUBLISHED_CONDITIONS`` desliga-os, como nos
    resultados recolhidos.

    Args:
        xmpp (bool): Ligar os agentes a um servidor XMPP em localhost em vez do transporte
            local.
        password (str): Palavra-passe das contas dos agentes.
        inspection_outcomes (dict[str, str] | None): Resultado fixo da inspeção por
            ``resource_id``, para testes determinísticos; os outros recursos usam
            ``Scenario.inspect``.
        interrupt_resource (str | None): ``resource_id`` cuja missão é interrompida uma vez,
            quando o recurso estiver fora da base; para testes determinísticos.
        max_seconds (float | None): Limite global, em segundos reais. None calcula um que
            cobre a verificação e as tentativas das duas fases de missão; um limite
            explícito mantém o watchdog do chamador.
        response_settings (dict | None): Ativa a Etapa 7 (``reputation``, ``policy``,
            ``sources``, ``severity`` e, opcionais, ``severity_by_source``,
            ``compatibility_rules`` e ``adjudication``). Com ``adjudication``, o avaliador
            atualiza ``reputation`` após a execução a partir dos MISSION_RESULT com
            cobertura suficiente.
        reputation (ReputationBook | None): Apenas aprendizagem previamente validada pelo
            avaliador; o sensor recebe uma cópia dos pesos. None cria uma nova a partir de
            ``response_settings["reputation"]``.
        faults (dict | None): Perda, atraso, duplicação e indisponibilidade só no transporte
            local (ver ``fault_settings``); não altera nem valida o servidor XMPP.
        scenario (dict | None): Cenário da Etapa 9, que substitui semente, fontes, eventos e
            recursos do MVP (ver ``scenario_settings``). A sua identidade (``run_id``) é
            também o âmbito da adjudicação.
        corroborate (bool): False ignora a resposta do par.
        selection_weights (dict[str, float] | None): Pesos passados a
            ``select_best_proposal``, ex. só ETA para "mais próximo".
        run_id (str | None): Identidade da execução; tem de coincidir com a do cenário quando
            ambos são fornecidos. None usa a do cenário ou ``mvp-seed-<seed>``. Sem cenário,
            repetir a mesma semente é replay para aprendizagem; uma nova amostra exige
            ``run_id`` explícito, que não prova independência estatística.
        extra_initiators (dict[str, Position] | None): Bloco F2: associa fontes do cenário a
            posições; cada uma ganha um sensor no mapa e um IncidentSensorAgent próprio, que
            só trata o que a sua fonte deteta. O runner não escolhe quem trata cada ameaça;
            os campos de topo do relatório continuam a ser os do sensor-mvp.
        extra_patrols (dict[str, Position] | None): C4 mínimo: associa novos IDs de patrulha
            a posições base; são drones com 100 % de autonomia.
        cfp_limit (int | None): K de C1: cada iniciador envia o CFP só aos K recursos com
            base mais próxima do alvo (K × ronda nas rondas seguintes). None envia a todos.
        max_receive_timeout (float | None): Teto do prazo dinâmico do iniciador, em segundos
            reais (ver ``configure_mvp``). Um ``receive_timeout`` acima do teto exige um
            teto maior (ou None).
        queue_rounds (int): Rondas da fila do iniciador quando os recursos estão ocupados.
        silent_invalid (bool): Os recursos ignoram um ACCEPT incoerente em vez de
            responderem ``reservation_failed``.
        queue_priority (bool): Ordenar a fila em cada recurso: primeiro a ocorrência mais
            grave e, em caso de empate, a que espera há mais tempo. A gravidade de cada
            iniciador vem de ``response_settings["severity"]`` ou, por fonte, de
            ``response_settings["severity_by_source"]``.
        corroboration_settings (dict[str, float] | None): ``max_distance`` e
            ``max_time_difference``, com omissões 3.0 células e 2.0 s simulados.
        receive_timeout (float | None): Prazo base, em segundos reais; None usa 0.5 s local
            ou 2.0 s XMPP. Não liga o prazo dinâmico do Bloco F.
        minimum_autonomy_percent (float): Reserva mínima de energia, em %, de todas as
            patrulhas e do guarda.
        extra_rangers (dict[str, Position] | None): Associa novos IDs de guarda a posições
            base.
        extra_informants (dict[str, Position] | None): Associa fontes do cenário a posições:
            cada uma ganha um InformantAgent, e cada iniciador adicional passa a corroborar
            com o informador mais próximo (sensor-2 incluído). Um dicionário vazio liga a
            corroboração só com o sensor-2; None: os iniciadores adicionais não corroboram.
        map_size (tuple[int, int]): Largura e altura do mapa (C4 completo), em células.
        sensor_positions (dict[str, Position] | None): Posições que substituem as de
            sensor-1 e/ou sensor-2 (C4 completo).
        expire_unseen (bool): Prazo de validade do iniciador (ver ``configure_mvp``);
            mitigação da espera na fila, desligada por omissão.
        queue_until_free (bool): A fila espera até ao ``busy_until`` da recusa (ver
            ``configure_mvp``); mitigação desligada por omissão.
        chain_missions (bool): O recurso aceita a missão seguinte durante o regresso à base;
            mitigação desligada por omissão.
        retransmit (int): N: o iniciador reenvia até N vezes o mesmo VERIFY_REQUEST, CFP ou
            ACCEPT quando a resposta não chega, e os recursos repetem a resposta já dada.
            0 desliga.
        alert_distance (float | None): D: liga o aviso entre iniciadores com cobertura
            sobreposta. Cada um envia um ALERT aos vizinhos e, se dois leram a mesma ameaça
            (até D células), só o que leu primeiro a trata; o outro fecha como
            ``duplicate_alert``. O runner só diz quem é vizinho. None desliga.

    Returns:
        dict: Relatório da execução: configuração efetiva, ``ground_truth``, decisão, estado
            e motivo do incidente, resultados, missões, recursos, falhas aplicadas,
            atualizações de reputação, ``timeline`` e mensagens trocadas.

    Raises:
        ValueError: Se as definições forem inválidas, se ``faults``, iniciadores,
            informadores ou recursos adicionais forem pedidos com XMPP, se ``run_id`` for
            vazio ou diferente do do cenário, ou se houver IDs repetidos ou não suportados.
        TimeoutError: Se a execução não terminar em ``max_seconds``.
        Exception: A exceção de uma tarefa (comportamento ou relógio) que falhou, relançada.
    """
    corroboration, receive_timeout, minimum_autonomy_percent = validate_experimental_settings(
        xmpp=xmpp, corroboration_settings=corroboration_settings, receive_timeout=receive_timeout,
        minimum_autonomy_percent=minimum_autonomy_percent, selection_weights=selection_weights)
    faults = fault_settings(faults)
    if faults is not None and xmpp:
        raise ValueError("A injeção de falhas só existe no transporte local.")
    seed, sources, events, resource_settings, prefix = scenario_settings(scenario)
    scenario_run_id = scenario["run_id"] if scenario is not None else None
    if run_id is None:
        run_id = scenario_run_id if scenario_run_id is not None else f"mvp-seed-{seed}"
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id deve identificar a execução de avaliação.")
    if scenario_run_id is not None and run_id != scenario_run_id:
        raise ValueError("run_id deve coincidir com scenario.run_id.")
    extra_initiators = dict(extra_initiators or {})
    extra_patrols, extra_rangers = dict(extra_patrols or {}), dict(extra_rangers or {})
    informants = dict(extra_informants or {})
    if (extra_initiators or extra_patrols or extra_rangers or informants) and xmpp:
        raise ValueError("Iniciadores, informadores e recursos adicionais só existem no transporte local.")
    if (set(extra_patrols) | set(extra_rangers)) & set(MVP_RESOURCES) or set(extra_patrols) & set(extra_rangers):
        raise ValueError("extra_patrols e extra_rangers exigem IDs diferentes entre si e de drone, vehicle e ranger.")
    if ((set(extra_initiators) | set(informants)) & {"sensor-1", "sensor-2"}
            or (set(extra_initiators) | set(informants)) - set(sources) or set(extra_initiators) & set(informants)):
        raise ValueError("extra_initiators e extra_informants exigem fontes do cenário distintas, "
                         "diferentes de sensor-1 e sensor-2.")
    base_sensors = {"sensor-1": Position(2, 2), "sensor-2": Position(4, 2)}
    if set(sensor_positions or {}) - set(base_sensors):
        raise ValueError("sensor_positions aceita apenas sensor-1 e sensor-2.")
    world = World(*map_size, {**base_sensors, **(sensor_positions or {}), **extra_initiators, **informants})
    scenario = Scenario(world, sources, events, seed=seed, observation_prefix=prefix)
    sensor = IncidentSensorAgent("sensor-mvp@localhost", password, "sensor-peer-mvp@localhost")
    peer = InformantAgent("sensor-peer-mvp@localhost", password)
    sensor.set_local_observation_feed(scenario.source("sensor-1"), 0.0)
    sensor.set_corroboration_context(("sensor-2",) if corroborate else (),
                                     corroboration["max_distance"], corroboration["max_time_difference"], 1,
                                     compatibility_rules=(response_settings or {}).get("compatibility_rules"))
    peers = {"sensor-2": peer}
    for source_id in informants:
        peers[source_id] = InformantAgent(f"{source_id}-mvp@localhost", password)
        peers[source_id].set_local_observation_feed(scenario.source(source_id), source_id, 0.0)
    extras = {}
    for source_id, position in extra_initiators.items():
        # C6: cada iniciador adicional pergunta ao informador mais próximo. Sem extra_informants
        # não corrobora (o sensor-2 responde, mas a resposta não conta), como no Bloco F2.
        # shortcut: os iniciadores adicionais não atualizam a reputação; alargar a adjudicação se for preciso.
        nearest = min(peers, key=lambda key: distance(world.sensors[key], position))
        extras[source_id] = extra = IncidentSensorAgent(
            f"{source_id}-mvp@localhost", password, str(peers[nearest].jid))
        extra.set_local_observation_feed(scenario.source(source_id), 0.0)
        extra.set_corroboration_context(
            (nearest,) if corroborate and extra_informants is not None else (),
            corroboration["max_distance"], corroboration["max_time_difference"], 1,
            compatibility_rules=(response_settings or {}).get("compatibility_rules"))
    initiators = [sensor, *extras.values()]
    if response_settings is not None:
        if reputation is None:
            reputation = ReputationBook(**response_settings["reputation"])
        for source_id, initiator in zip(("sensor-1", *extras), initiators):
            initiator.set_response_policy(
                ResponsePolicy(**response_settings["policy"]),
                reputation.snapshot(world.sensors), response_settings["sources"],
                severity=response_settings.get("severity_by_source", {}).get(
                    source_id, response_settings["severity"]),
                default_reputation=reputation.score("sensor-1"),
            )
    peer.set_local_observation_feed(scenario.source("sensor-2"), "sensor-2", 0.0)
    mobiles = []
    for agent_class, name, capability in (
        (DroneAgent, "drone", "mobile_verification"),
        (VehicleAgent, "vehicle", "mobile_verification"),
        (RangerAgent, "ranger", "incident_response"),
        *((DroneAgent, name, "mobile_verification") for name in extra_patrols),
        *((RangerAgent, name, "incident_response") for name in extra_rangers),
    ):
        options = resource_settings.get(name, {})
        origin = (model_from_dict(options["position"], Position) if "position" in options
                  else {**MVP_RESOURCES, **extra_patrols, **extra_rangers}[name])
        world.validate_position(origin)
        kind = "drone" if name in extra_patrols else "ranger" if name in extra_rangers else name
        agent = agent_class(f"{name}-mvp@localhost", password,
                            ResourceState(name, kind, origin, True,
                                          options.get("autonomy_percent", 100.0)),
                            (capability,), minimum_autonomy_percent=minimum_autonomy_percent, eta_seconds=0.0,
                            energy_cost_percent=0.0, load=options.get("load", 0.0))
        outcome = (inspection_outcomes or {}).get(name)
        inspect = scenario.inspect if outcome is None else lambda position, now, task, value=outcome: value
        agent.configure_execution(world, inspect)
        agent.silent_invalid, agent.ordered_queue = silent_invalid, queue_priority
        agent.chain_missions, agent.resend_replies = chain_missions, bool(retransmit)
        mobiles.append(agent)
    jids = lambda capability, present: {str(a.jid): a.resource.resource_id for a in mobiles
                                        if (capability in a.capabilities) is present}
    initiator_ids = ("sensor-1", *extras)
    for source_id, initiator in zip(initiator_ids, initiators):
        # Vizinhos: iniciadores cujo alcance se pode sobrepor ao deste (posições e alcances são do ambiente).
        neighbours = () if alert_distance is None else tuple(
            str(other.jid) for other_id, other in zip(initiator_ids, initiators) if other is not initiator
            and distance(world.sensors[source_id], world.sensors[other_id])
            <= sources[source_id].detection_range + sources[other_id].detection_range + alert_distance)
        initiator.configure_mvp(jids("incident_response", False), jids("incident_response", True),
                                receive_timeout=receive_timeout,
                                selection_weights=selection_weights, cfp_limit=cfp_limit,
                                max_receive_timeout=max_receive_timeout, queue_rounds=queue_rounds,
                                expire_unseen=expire_unseen, queue_until_free=queue_until_free,
                                retransmit=retransmit, neighbours=neighbours, alert_distance=alert_distance,
                                base_positions={str(a.jid): a.resource.position for a in mobiles})
    initial_resources = [model_to_dict(agent.resource) for agent in mobiles]
    if max_seconds is None:
        # Cada tentativa espera propostas, STATUS e até 10 prazos pelo resultado.
        # Há, no máximo, verificação móvel e intervenção do guarda, mais margem
        # para o regresso e o encerramento depois dos timeouts operacionais.
        max_seconds = (sensor_module.RESPONSE_TIMEOUT_SECONDS
                       + 2 * sensor.max_attempts * (1 + retransmit)
                       * ((1 + queue_rounds) * 2 * sensor.max_receive_timeout
                          + (10 + queue_rounds) * sensor.receive_timeout) + 1.0)
    agents = [*mobiles, *peers.values(), *initiators]
    tasks, started, transcript, fault_log = [], [], [], []
    rng = random.Random(faults["seed"] if faults else 0)
    by_resource = {agent.resource.resource_id: agent for agent in mobiles}

    async def clock_loop():
        """Avançar o cenário 1 s simulado por ciclo enquanto houver missão em execução.

        Propaga a nova hora a iniciadores, informadores e recursos móveis e
        interrompe, uma única vez, a missão de ``interrupt_resource`` quando este
        está fora da base.
        """
        interrupted = False
        while True:
            await asyncio.sleep(0.01)
            # O tempo físico só avança enquanto existe uma missão em execução.
            # A negociação continua a ter timeout real independente.
            if any(a.execution is not None and not a.execution.finished for a in mobiles):
                now = scenario.advance(1.0)
                # Pedidos e respostas de verificação levam a hora atual, não a do arranque.
                for initiator in initiators:
                    initiator.simulated_time = initiator.created_at = now
                for informant in peers.values():
                    informant.created_at = now
                for agent in mobiles:
                    agent.set_simulated_time(now)
                    if (not interrupted and agent.resource.resource_id == interrupt_resource
                            and agent.execution is not None and not agent.execution.finished
                            and agent.execution.resource.position != agent.execution.home):
                        agent.execution.interrupt()
                        interrupted = True

    async def local_behaviour(behaviour):
        """Repetir ``run`` do comportamento; um OneShotBehaviour corre uma só vez."""
        while True:
            await behaviour.run()
            if isinstance(behaviour, OneShotBehaviour):
                return

    try:
        if xmpp:
            for agent in agents:
                await agent.start(auto_register=True)
                started.append(agent)
        else:
            for agent in agents:
                await agent.setup()
            routes = {str(agent.jid): agent.behaviours for agent in agents}
            for agent in agents:
                for behaviour in agent.behaviours:
                    inbox = asyncio.Queue()
                    behaviour._local_inbox = inbox

                    async def receive(timeout=None, queue=inbox):
                        """Ler da caixa local; devolve None se o prazo expirar."""
                        try:
                            return await asyncio.wait_for(queue.get(), timeout)
                        except TimeoutError:
                            return None

                    async def deliver(message, delay=0.0):
                        """Entregar a mensagem, após o atraso, a quem tiver um template compatível."""
                        if delay:
                            await asyncio.sleep(delay)
                        for target in routes.get(str(message.to), ()):
                            if target.template is not None and target.template.match(message):
                                await target._local_inbox.put(message)

                    async def send(message, sender=str(agent.jid)):
                        """Registar no transcript e entregar com as falhas configuradas.

                        Sem ``faults`` a entrega é direta. Com falhas, pode gerar
                        lixo (flood), perder a mensagem, ocupar o recurso depois
                        de um PROPOSAL, duplicar ou atrasar; cada falha aplicada
                        fica em ``fault_log``.
                        """
                        message.sender = sender
                        body = json.loads(message.body)
                        transcript.append({"sender": sender, "to": str(message.to), "body": body})
                        if faults is None:
                            return await deliver(message)
                        kind = body["message_type"]
                        ends = {sender.split("@")[0], str(message.to).split("@")[0]}
                        entry = {"message_id": body["message_id"], "type": kind, "to": str(message.to)}
                        if faults["flood"] and not any(
                                "junk-" in str(v) for v in (message.body, message.get_metadata("in-reply-to"))):
                            # Lixo derivado da mensagem real, para o mesmo destinatário: JSON
                            # partido, IDs trocados e data fora de prazo. Um CFP com IDs
                            # novos seria um pedido válido, por isso não leva essa variante.
                            # As respostas ao lixo não geram mais lixo.
                            tag = f"junk-{len(fault_log)}"
                            for i in range(faults["flood"]):
                                for junk_body in ("{", *(() if kind == "CFP" else (json.dumps(
                                        {**body, "message_id": f"{tag}-{i}-ids", "incident_id": "incident-junk",
                                         "mission_id": "mission-junk"}),)), json.dumps(
                                        {**body, "message_id": f"{tag}-{i}-late",
                                         "created_at": body["created_at"] + 1e6})):
                                    junk = copy(message)
                                    junk.body = junk_body
                                    await deliver(junk)
                            fault_log.append({"fault": "flood", **entry})
                        if (kind in faults["drop"] or ends & set(faults["unavailable_agents"])
                                or (faults["loss"] and rng.random() < faults["loss"])):
                            fault_log.append({"fault": "lost", **entry})
                            return
                        if kind == "PROPOSAL" and body["source_id"] in faults["occupied_after_proposal"]:
                            # O recurso é tomado por outra missão entre PROPOSAL e ACCEPT.
                            by_resource[body["source_id"]].reservation.reserve(
                                "external-mission", resource_id=body["source_id"])
                            fault_log.append({"fault": "occupied", **entry})
                        copies = 2 if kind in faults["duplicate"] else 1
                        delay = faults["delay"].get(kind, 0.0)
                        if copies == 2:
                            fault_log.append({"fault": "duplicated", **entry})
                        if delay:
                            fault_log.append({"fault": "delayed", "seconds": delay, **entry})
                        for _ in range(copies):
                            if delay:
                                tasks.append(asyncio.create_task(deliver(message, delay)))
                            else:
                                await deliver(message)
                    behaviour.receive, behaviour.send = receive, send
            tasks.extend(asyncio.create_task(local_behaviour(b)) for a in agents for b in a.behaviours)
        tasks.append(asyncio.create_task(clock_loop()))
        async with asyncio.timeout(max_seconds):
            while (not all(i.cycle_done for i in initiators)
                   or any(a.execution and not a.execution.finished for a in mobiles)):
                for task in tasks:
                    if task.done() and not task.cancelled() and task.exception():
                        raise task.exception()
                await asyncio.sleep(0.005)
        updates = []
        adjudication = (response_settings or {}).get("adjudication")
        if adjudication is not None and sensor.incident_state is not None:
            incident_id = sensor.incident_state.incident_id
            # Avaliador: o sensor já terminou; nenhuma atualização volta à decisão desta execução.
            updates = [reputation.update(obs, incident_id,
                                         result_from_mission(result, obs, incident_id, **adjudication),
                                         run_id=run_id)
                       for result in sensor.results for obs in sensor.incident_observations]
        timeline = sorted([
            *sensor.timeline,
            *({**entry, "initiator": source_id} for source_id, extra in extras.items()
              for entry in extra.timeline),
            *(entry for agent in mobiles for execution in agent.executions for entry in execution.timeline),
        ], key=lambda entry: entry["time"])
        return {"transport": "xmpp" if xmpp else "local",
                "run_id": run_id,
                "response_settings": response_settings,
                "scenario_seed": seed, "faults": faults, "fault_log": fault_log,
                "corroborate": corroborate, "selection_weights": selection_weights,
                "corroboration_settings": corroboration, "receive_timeout": receive_timeout,
                "minimum_autonomy_percent": minimum_autonomy_percent,
                # Só para o avaliador, depois de a execução terminar.
                "ground_truth": scenario.ground_truth,
                "world": {"width": world.width, "height": world.height,
                          "sensors": {key: model_to_dict(p) for key, p in world.sensors.items()}},
                "initial_resources": initial_resources,
                "reputation_scores": sensor.reputation_scores,
                "reputation_updates": updates,
                "decision": sensor.decision, "verification": sensor.verification_history,
                "incident_status": sensor.incident_state.status.value if sensor.incident_state else None,
                "reason": sensor.close_reason,
                "results": [result.to_dict() for result in sensor.results],
                "missions": [model_to_dict(mission) for mission in sensor.missions],
                "resources": [model_to_dict(agent.reservation.resource_state) for agent in mobiles],
                "reservations": [agent.reservation.reserved_mission_id for agent in mobiles],
                "extra_initiators": {source_id: {
                    "decision": extra.decision,
                    "incident_status": extra.incident_state.status.value if extra.incident_state else None,
                    "reason": extra.close_reason,
                    "results": [result.to_dict() for result in extra.results],
                    "missions": [model_to_dict(mission) for mission in extra.missions],
                } for source_id, extra in extras.items()},
                "timeline": timeline, "messages": transcript}
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
        for agent in reversed(started):
            await agent.stop()


def main():
    """Ler os argumentos, correr run_mvp e imprimir o relatório em JSON.

    Raises:
        SystemExit: Via ``parser.error``, se ``--faults`` for usado com ``--xmpp`` ou se
            ``--xmpp`` for pedido sem a variável XMPP_PASSWORD.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xmpp", action="store_true", help="Usar servidor XMPP em localhost")
    parser.add_argument("--policy", metavar="JSON", help="Ativar a política da Etapa 7 com esta configuração")
    parser.add_argument("--faults", metavar="JSON", help="Injetar falhas da Etapa 8 no transporte local")
    parser.add_argument("--run-id", help="Identificar uma nova amostra de avaliação; repetir o ID é replay")
    args = parser.parse_args()
    settings = faults = None
    if args.policy:
        with open(args.policy, encoding="utf-8") as stream:
            settings = json.load(stream)
    if args.faults:
        if args.xmpp:
            parser.error("--faults só funciona com o transporte local.")
        with open(args.faults, encoding="utf-8") as stream:
            faults = json.load(stream)
    password = os.environ.get("XMPP_PASSWORD", "local-demo")
    if args.xmpp and "XMPP_PASSWORD" not in os.environ:
        parser.error("Defina XMPP_PASSWORD para as cinco contas locais do MVP.")
    async def demo():
        """Correr run_mvp com os argumentos recebidos e imprimir o relatório."""
        print(json.dumps(await run_mvp(xmpp=args.xmpp, password=password,
                                      response_settings=settings, faults=faults, run_id=args.run_id),
                         ensure_ascii=False, indent=2))
    if args.xmpp:
        import spade
        spade.run(demo())
    else:
        asyncio.run(demo())


if __name__ == "__main__":
    main()

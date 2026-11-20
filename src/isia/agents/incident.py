"""Ciclo local de um incidente iniciado pelo próprio sensor, sem despachante.

Por onde começar:

- `IncidentSensorAgent.IncidentBehaviour.run`: o ciclo completo, do alerta ao fecho.
- `IncidentSensorAgent.IncidentBehaviour.allocate`: uma ronda de Contract Net, com renegociação.
- `IncidentSensorAgent.IncidentBehaviour.execute_task`: alocar uma missão e repetir com outro recurso se falhar.
- `IncidentSensorAgent.configure_mvp`: parâmetros (prazos, fila, limite de CFP, vizinhos).
"""

import asyncio
from dataclasses import replace
import logging
from time import monotonic

from spade.template import Template

from isia.agents.sensor import SensorAgent, _recent_observations
from isia.communication.messages import Message, MessageType, model_from_dict, model_to_dict
from isia.communication.transport import (
    ONTOLOGY, CONTRACT_NET_PROTOCOL, bare_jid as bare, build_spade_message, parse_spade_message,
)
from isia.domain.incident_state import IncidentState, IncidentStatus
from isia.domain.models import Bid, Incident, Mission, MissionStatus, Observation, Position
from isia.domain.validation import is_finite_number
from isia.reasoning.allocation import (
    MissionRegistry, build_cfp_message, build_accept_message,
    build_proposal_rejection_message, select_best_proposal,
    reservation_status_matches_accept, RANGER_TASK, RANGER_CAPABILITY,
)
from isia.reasoning.corroboration import are_observations_compatible


logger = logging.getLogger(__name__)
QUEUE_INTERVAL_SECONDS = 5.0  # tempo simulado entre dois pedidos a um recurso ocupado


class IncidentSensorAgent(SensorAgent):
    """O sensor corrobora, negoceia, recebe resultados e encerra a ocorrência.

    Os atributos abaixo só existem depois de ``configure_mvp``.

    Attributes:
        patrols (dict[str, str]): ``resource_id`` de cada patrulha de verificação, por JID.
        rangers (dict[str, str]): ``resource_id`` de cada ranger, por JID.
        receive_timeout (float): Prazo real curto, em segundos, para propostas e avisos de vizinhos.
        max_receive_timeout (float): Teto do prazo dinâmico e da espera pela confirmação.
        max_attempts (int): Missões a tentar, cada uma com outro recurso, antes de desistir.
        queue_rounds (int): Pedidos repetidos com os recursos ocupados; 0 desliga a fila.
        queue_until_free (bool): Se a espera na fila vai até ao ``busy_until`` da recusa.
        expire_unseen (bool): Se fecha como expirado quando o feed deixa de ver a ameaça.
        retransmit (int): Reenvios do mesmo pedido sem resposta; 0 desliga o reenvio.
        cfp_limit (int | None): K de C1 (CFP só aos K recursos mais próximos); None envia a todos.
        base_positions (dict[str, Position]): Posição base de cada recurso, por JID.
        selection_weights (dict[str, float]): Pesos passados a ``select_best_proposal``.
        neighbours (tuple[str, ...]): JIDs dos iniciadores vizinhos; vazio sem ``alert_distance``.
        alert_distance (float | None): Distância, em células, para dois alertas serem a mesma
            ameaça; None desliga o aviso entre iniciadores.
        simulated_time (float): Instante simulado atual, avançado pelo runner.
        incident_state (IncidentState | None): Estado da ocorrência; None antes do alerta.
        timeline (list[dict[str, object]]): Cronologia de eventos, com o instante simulado.
        results (list[Message]): MISSION_RESULT aceites, por ordem de chegada.
        missions (list[Mission]): Missões terminadas, em ``DONE`` ou ``FAILED``.
        incident_observations (tuple[Observation, ...]): Leituras do feed que abriram a ocorrência.
        cycle_done (bool): True quando o ciclo terminou, com ou sem incidente.
        close_reason (str | None): Motivo do fecho (ex.: ``confirmed``, ``threat_expired``).
        behaviour (IncidentBehaviour): Comportamento registado em ``setup``.
    """

    def configure_mvp(self, patrols, rangers, *, receive_timeout=2.0, max_attempts=2,
                      selection_weights=None, base_positions=None, cfp_limit=None,
                      max_receive_timeout=None, queue_rounds=0, expire_unseen=False,
                      queue_until_free=False, retransmit=0, neighbours=(), alert_distance=None):
        """Configurar a ocorrência do MVP.

        Também reinicia a cronologia, os resultados e o estado do incidente.

        Args:
            patrols (Mapping[str, str]): ``resource_id`` de cada patrulha de verificação, por JID.
            rangers (Mapping[str, str]): ``resource_id`` de cada ranger, por JID.
            receive_timeout (float): Prazo real, em segundos, para propostas e avisos de
                vizinhos; tem de ser positivo.
            max_attempts (int): Missões a tentar, cada uma com outro recurso; pelo menos 1.
            selection_weights (Mapping[str, float] | None): Pesos de ``select_best_proposal``
                (ex.: ``eta_weight``); None usa os valores por omissão.
            base_positions (Mapping[str, Position] | None): Posição base de cada recurso, por JID.
            cfp_limit (int | None): K de C1: com ``base_positions`` de todos os candidatos, o CFP
                só vai aos K recursos mais próximos do alvo (K x ronda nas rondas seguintes).
                None envia a todos.
            max_receive_timeout (float | None): Ativa o prazo dinâmico: sem nenhuma proposta ao
                fim de ``receive_timeout``, o iniciador espera até este teto; o STATUS espera
                sempre até ao teto. None: igual a ``receive_timeout``.
            queue_rounds (int): Ativa a fila: com os recursos ocupados, o iniciador espera
                ``QUEUE_INTERVAL_SECONDS`` simulados e volta a pedir, até este número de vezes.
            expire_unseen (bool): Ativa o prazo de validade: antes de cada ronda de CFP o
                iniciador volta a ler o seu sensor; sem nenhuma leitura na janela do feed,
                fecha como expirado e não manda ninguém.
            queue_until_free (bool): Se a recusa trouxer ``busy_until``, a fila espera até esse
                instante em vez do intervalo.
            retransmit (int): Ativa o reenvio: sem resposta no prazo, o mesmo VERIFY_REQUEST,
                CFP (só sem nenhuma proposta e só a quem não respondeu) ou ACCEPT (mesmo
                ``message_id``) volta a sair, até este número de vezes.
            neighbours (Iterable[str]): JIDs de outros iniciadores; ignorado sem
                ``alert_distance``.
            alert_distance (float | None): Ativa o aviso entre iniciadores: cada um envia um ALERT
                aos vizinhos e desiste se um deles viu a mesma ameaça, a esta distância em
                células, primeiro e confirma que fica com ela. None desliga o aviso.

        Raises:
            ValueError: Se ``max_attempts``, ``cfp_limit``, ``queue_rounds`` ou ``retransmit``
                não forem inteiros no intervalo válido, se um prazo ou ``alert_distance`` for
                negativo ou não finito, se ``receive_timeout`` for 0 ou se
                ``max_receive_timeout`` for inferior a ``receive_timeout``.
        """
        if type(max_attempts) is not int or max_attempts < 1:
            raise ValueError("max_attempts deve ser positivo.")
        if cfp_limit is not None and (type(cfp_limit) is not int or cfp_limit < 1):
            raise ValueError("cfp_limit deve ser um inteiro positivo.")
        from isia.simulation.movement import nonnegative
        self.base_positions = {bare(jid): position for jid, position in (base_positions or {}).items()}
        self.cfp_limit = cfp_limit
        nonnegative(receive_timeout, "receive_timeout")
        if receive_timeout == 0:
            raise ValueError("receive_timeout deve ser positivo.")
        if max_receive_timeout is not None:
            nonnegative(max_receive_timeout, "max_receive_timeout")
            if max_receive_timeout < receive_timeout:
                raise ValueError("max_receive_timeout não pode ser inferior a receive_timeout.")
        self.max_receive_timeout = max_receive_timeout or receive_timeout
        if type(queue_rounds) is not int or queue_rounds < 0:
            raise ValueError("queue_rounds deve ser um inteiro não negativo.")
        self.queue_rounds = queue_rounds
        if type(retransmit) is not int or retransmit < 0:
            raise ValueError("retransmit deve ser um inteiro não negativo.")
        self.retransmit = retransmit
        if alert_distance is not None:
            nonnegative(alert_distance, "alert_distance")
        self.neighbours = tuple(bare(jid) for jid in neighbours) if alert_distance is not None else ()
        self.alert_distance = alert_distance
        self.expire_unseen, self.queue_until_free = expire_unseen, queue_until_free
        self.patrols, self.rangers = dict(patrols), dict(rangers)
        self.receive_timeout, self.max_attempts = receive_timeout, max_attempts
        self.selection_weights = dict(selection_weights or {})
        self.simulated_time = self.created_at or 0.0
        self.incident_state = None
        self.timeline = []
        self.results = []
        self.missions = []
        self.incident_observations = ()
        self.cycle_done = False
        self.close_reason = None

    @property
    def severity_level(self):
        """Classificar a gravidade em três níveis, para a prioridade da missão: 0 leve, 1 média, 2 grave.

        Grave a partir de ``severe_threshold`` da política (0.8 sem política); média a partir de
        metade desse limiar.

        Returns:
            int: Nível de gravidade, 0, 1 ou 2.
        """
        severe = self.response_policy.severe_threshold if self.response_policy else 0.8
        return 2 if self.severity >= severe else 1 if self.severity >= severe / 2 else 0

    def record(self, event, **details):
        """Acrescentar à cronologia um evento com o instante simulado e os detalhes.

        Args:
            event (str): Nome do evento (ex.: ``ALERT``, um tipo de mensagem ou um estado).
            **details: Campos extra guardados com o evento.
        """
        self.timeline.append({"time": self.simulated_time, "event": event, **details})

    def transition(self, status):
        """Mudar o estado do incidente e registar o novo estado na cronologia.

        Propaga o ValueError de ``change_status`` numa transição não permitida.

        Args:
            status (IncidentStatus): Novo estado do incidente.
        """
        self.incident_state = self.incident_state.change_status(status)
        self.record(status.value)

    class IncidentBehaviour(SensorAgent.VerificationBehaviour):
        """Ciclo único: alerta, verificação, decisão, Contract Net e fecho."""
        def result_matches_assignment(self, incoming, result, assignment, mission):
            """Verificar se um resultado corresponde à missão atribuída.

            Vale para resultados normais e antecipados.

            Args:
                incoming (spade.message.Message): Mensagem SPADE recebida.
                result (Message | None): Corpo já interpretado; None se for inválido.
                assignment (tuple[str, Message, str]): ``(jid, accept, resource_id)`` devolvido
                    por ``allocate``.
                mission (Mission): Missão atribuída.

            Returns:
                bool: True se for um MISSION_RESULT ``inform`` do recurso escolhido, em resposta a
                    este ACCEPT, com a mesma missão e tarefa e emitido até ao instante simulado
                    atual.
            """
            jid, accept, resource_id = assignment
            return (result is not None and result.message_type is MessageType.MISSION_RESULT
                    and bare(incoming.sender) == jid and bare(incoming.to) == bare(self.agent.jid)
                    and incoming.get_metadata("performative") == "inform"
                    and incoming.get_metadata("in-reply-to") == accept.message_id
                    and result.mission_id == accept.mission_id
                    and result.incident_id == accept.incident_id
                    and result.conversation_id == accept.conversation_id
                    and result.source_id == resource_id
                    and result.payload.get("resource_id") == resource_id
                    and result.payload.get("accept_message_id") == accept.message_id
                    and result.payload["task"] == mission.task
                    and accept.created_at <= result.payload["completed_at"] <= result.created_at
                    and result.created_at <= self.agent.simulated_time)

        async def send_body(self, recipient, body, performative, reply_to=None):
            """Registar a mensagem na cronologia e enviá-la por Contract Net.

            Args:
                recipient (str): JID do destinatário.
                body (Message): Corpo a enviar.
                performative (str): Performativa FIPA (ex.: ``cfp``, ``accept-proposal``).
                reply_to (str | None): ``message_id`` a que responde; None se não for resposta.
            """
            self.agent.record(body.message_type.value, recipient=recipient,
                              mission_id=body.mission_id, payload=body.payload)
            await self.send(build_spade_message(
                recipient, body, performative=performative,
                conversation_id=body.conversation_id, in_reply_to=reply_to,
                protocol=CONTRACT_NET_PROTOCOL))

        async def receive_until(self, deadline):
            """Receber até ao prazo real ``deadline``; None se o prazo passar.

            Args:
                deadline (float): Prazo, no relógio de ``time.monotonic``.

            Returns:
                tuple[spade.message.Message, Message | None] | None: ``(incoming, None)`` se o
                    corpo for inválido ou tiver sido emitido depois do instante simulado atual;
                    caso contrário, ``(incoming, corpo)``. None se o prazo passar.
            """
            remaining = deadline - monotonic()
            if remaining <= 0:
                return None
            incoming = await self.receive(timeout=remaining)
            if incoming is None or monotonic() >= deadline:
                return None
            try:
                body = parse_spade_message(incoming, expected_protocol=CONTRACT_NET_PROTOCOL)
            except (TypeError, ValueError):
                return (incoming, None)
            if body.created_at > self.agent.simulated_time:
                return (incoming, None)
            return incoming, body

        async def yields_to_neighbour(self, observation, incident_id):
            """Avisar os iniciadores vizinhos e dizer se um deles fica com esta ameaça.

            Prioridade: a leitura mais antiga e, em caso de empate, o menor source_id. Os dois
            lados calculam a mesma ordem, por isso só um desiste. Um ALERT perdido deixa os dois
            a tratar a mesma ameaça, como sem aviso.
            Segunda volta: cada um diz aos vizinhos que lhe cederiam se fica com a ameaça. Só se
            cede a quem fica; assim, numa fila de ameaças vizinhas, quem cederia a um vizinho que
            também desistiu trata a sua. Um veredicto perdido conta como «não fica»: os dois tratam.

            Args:
                observation (Observation): Leitura que abriu a ocorrência.
                incident_id (str): Identificador do incidente local.

            Returns:
                bool: True se um vizinho com prioridade fica com a ameaça e este iniciador desiste.
            """
            agent = self.agent
            key = (observation.observed_at, observation.source_id)

            def notice(message_id, payload):
                """Construir um ALERT sobre esta observação com o payload dado."""
                return Message(message_id, MessageType.ALERT, agent.simulated_time, payload,
                               event_id=observation.event_id, incident_id=incident_id,
                               source_id=observation.source_id, conversation_id=f"alert-{observation.event_id}")

            async def tell(jids, message):
                """Enviar a mesma mensagem, como ``inform``, a cada JID indicado."""
                for jid in jids:
                    await self.send(build_spade_message(
                        jid, message, performative="inform", conversation_id=message.conversation_id))

            await tell(agent.neighbours, notice(f"alert-{observation.event_id}", {
                "event_type": observation.event_type, "position": model_to_dict(observation.position),
                "observed_at": observation.observed_at, "confidence_score": observation.confidence_score}))
            # Vizinhos com a mesma ameaça: os que têm prioridade sobre mim, os que me cederiam e os veredictos.
            earlier, later, verdicts, heard = {}, [], {}, set()
            start = monotonic()

            async def listen(deadline):
                """Ler um ALERT ou um veredicto de um vizinho; False quando o prazo acaba."""
                remaining = deadline - monotonic()
                incoming = await self.receive(timeout=remaining) if remaining > 0 else None
                if incoming is None:
                    return False
                sender = bare(incoming.sender)
                try:
                    body = parse_spade_message(incoming)
                    if body.message_type is not MessageType.ALERT or sender not in agent.neighbours:
                        return True
                    if "keeps" in body.payload:
                        verdicts[sender] = body.payload["keeps"] is True
                        return True
                    other = Observation(
                        body.event_id, body.source_id, body.payload["event_type"],
                        model_from_dict(body.payload["position"], Position),
                        body.payload["observed_at"], body.payload["confidence_score"])
                    same = are_observations_compatible(
                        observation, other, agent.alert_distance, agent.max_time_difference)
                except (KeyError, TypeError, ValueError):
                    return True
                if sender not in heard:
                    heard.add(sender)
                    if same and (other.observed_at, other.source_id) < key:
                        earlier[sender] = other
                    elif same:
                        later.append(sender)
                return True

            # shortcut: um vizinho sem leitura não responde e a espera dura o prazo todo; se pesar, ele que diga «nada».
            while len(heard) < len(agent.neighbours) and await listen(start + agent.receive_timeout):
                pass
            await tell(later, notice(f"alert-{observation.event_id}-verdict", {"keeps": not earlier}))
            # Um vizinho pode demorar o prazo todo na primeira volta: o veredicto dele chega até ao dobro.
            while any(jid not in verdicts for jid in earlier) and await listen(start + 2 * agent.receive_timeout):
                pass
            for jid, other in earlier.items():
                if verdicts.get(jid):
                    agent.record("duplicate_alert", observation_id=other.event_id, source_id=other.source_id)
                    return True
            return False

        async def allocate(self, mission, candidates, attempt):
            """Fazer uma ronda de Contract Net e devolver ``(atribuição, falha)``.

            Envia o CFP, recolhe propostas e recusas válidas, aceita a melhor e rejeita
            as restantes. A atribuição ``(jid, accept, resource_id)`` só é devolvida
            depois de o recurso confirmar a reserva; senão devolve None e
            ``no_eligible_proposals``, ``confirmation_unknown`` ou
            ``reservation_rejected``. Um MISSION_RESULT que chegue antes da confirmação
            fica guardado para ``mission_result``.

            Args:
                mission (Mission): Missão a alocar.
                candidates (dict[str, str]): ``resource_id`` de cada recurso candidato, por JID.
                attempt (int): Número da ronda, a partir de 1; com ``cfp_limit``, alarga o CFP a
                    K x ronda recursos.

            Returns:
                tuple[tuple[str, Message, str] | None, str | None]: ``((jid, accept,
                    resource_id), None)`` com a reserva confirmada, ou ``(None, motivo)``.
            """
            agent = self.agent
            if agent.cfp_limit is not None and all(jid in agent.base_positions for jid in candidates):
                # C1: só os K mais próximos da base ao alvo; cada nova ronda alarga a K * ronda.
                # shortcut: usa a posição base, não a atual; trocar quando os recursos a anunciarem.
                from isia.simulation.movement import distance
                nearest = sorted(candidates, key=lambda jid: distance(agent.base_positions[jid], mission.target))
                candidates = {jid: candidates[jid] for jid in nearest[:agent.cfp_limit * attempt]}
            # Um único resultado, apenas durante a confirmação deste ACCEPT.
            self._pending_mission_result = None
            cfp = build_cfp_message(mission, agent.simulated_time,
                                    agent.simulated_time + 100, round_number=attempt)
            for jid in candidates:
                await self.send_body(jid, cfp, "cfp")
            responses = {}
            deadline = monotonic() + agent.receive_timeout
            ceiling = deadline - agent.receive_timeout + agent.max_receive_timeout
            resends = agent.retransmit
            while len(responses) < len(candidates):
                # Prazo dinâmico: com uma proposta na mão vale o prazo curto; sem nenhuma, o teto.
                proposed = any(r.message_type is MessageType.PROPOSAL for r in responses.values())
                received = await self.receive_until(deadline if proposed else ceiling)
                if received is None:
                    if proposed or not resends:
                        break
                    # Reenvio: sem nenhuma proposta, o mesmo CFP volta a sair para quem ficou calado.
                    resends -= 1
                    for jid in candidates:
                        if jid not in responses:
                            await self.send_body(jid, cfp, "cfp")
                    deadline = monotonic() + agent.receive_timeout
                    ceiling = deadline - agent.receive_timeout + agent.max_receive_timeout
                    continue
                incoming, body = received
                sender = bare(incoming.sender)
                if body is None or sender not in candidates or sender in responses:
                    continue
                if not (body.message_type in (MessageType.PROPOSAL, MessageType.REJECT)
                        and body.incident_id == cfp.incident_id and body.mission_id == cfp.mission_id
                        and body.conversation_id == cfp.conversation_id
                        and body.source_id == candidates[sender]
                        and body.payload.get("cfp_message_id") == cfp.message_id
                        and incoming.get_metadata("in-reply-to") == cfp.message_id
                        and incoming.get_metadata("performative") == (
                            "propose" if body.message_type is MessageType.PROPOSAL else "refuse")
                        and cfp.created_at <= body.created_at <= cfp.payload["deadline"]):
                    continue
                if body.message_type is MessageType.PROPOSAL:
                    try:
                        bid = model_from_dict(body.payload.get("bid"), Bid)
                    except (TypeError, ValueError):
                        continue
                    if bid.mission_id != cfp.mission_id or bid.resource_id != candidates[sender]:
                        continue
                responses[sender] = body
            selection = select_best_proposal(cfp, responses.values(), **agent.selection_weights)
            winner = selection.winner
            if winner is None:
                self._busy = any(r.payload.get("reason") in ("resource_unavailable", "waiting_turn") for r in responses.values())
                self._free_at = min((r.payload["busy_until"] for r in responses.values()
                                     if is_finite_number(r.payload.get("busy_until"))), default=None)
                return None, "no_eligible_proposals"
            winner_jid = next(jid for jid, body in responses.items() if body.message_id == winner.message_id)
            accept = build_accept_message(cfp, winner, agent.simulated_time, source_id=bare(agent.jid))
            await self.send_body(winner_jid, accept, "accept-proposal", winner.message_id)
            for jid, proposal in responses.items():
                if proposal.message_type is MessageType.PROPOSAL and jid != winner_jid:
                    rejection = build_proposal_rejection_message(cfp, proposal, agent.simulated_time)
                    try:
                        await self.send_body(jid, rejection, "reject-proposal", proposal.message_id)
                    except Exception as error:
                        logger.warning("REJECT não enviado a %s para a missão %s: %s",
                                       jid, mission.mission_id, error)
            assignment = (winner_jid, accept, winner.source_id)
            # Depois do ACCEPT não há alternativa: desistir cedo só dá confirmation_unknown.
            deadline = monotonic() + agent.max_receive_timeout
            confirmed = False
            resends = agent.retransmit
            try:
                while True:
                    received = await self.receive_until(deadline)
                    if received is None:
                        if not resends:
                            return None, "confirmation_unknown"
                        # Reenvio: o recurso repete a confirmação que já deu a este ACCEPT.
                        resends -= 1
                        await self.send_body(winner_jid, accept, "accept-proposal", winner.message_id)
                        deadline = monotonic() + agent.max_receive_timeout
                        continue
                    incoming, status = received
                    if self.result_matches_assignment(incoming, status, assignment, mission):
                        if self._pending_mission_result is None:
                            self._pending_mission_result = received
                        continue
                    if (status is not None and bare(incoming.sender) == winner_jid
                            and incoming.get_metadata("in-reply-to") == accept.message_id
                            and incoming.get_metadata("performative") == "inform"
                            and reservation_status_matches_accept(status, accept, winner.source_id)):
                        if status.payload["status"] != "reserved":
                            return None, "reservation_rejected"
                        confirmed = True
                        agent.record("reserved", resource_id=winner.source_id, mission_id=mission.mission_id)
                        return assignment, None
            finally:
                if not confirmed:
                    self._pending_mission_result = None

        async def mission_result(self, assignment, mission):
            """Esperar o MISSION_RESULT da atribuição; None se o prazo real se esgotar.

            Começa pelo resultado antecipado guardado em ``allocate``. O prazo é dez
            vezes ``receive_timeout`` e renova-se a cada reenvio do ACCEPT.

            Args:
                assignment (tuple[str, Message, str]): ``(jid, accept, resource_id)`` devolvido
                    por ``allocate``.
                mission (Mission): Missão atribuída.

            Returns:
                Message | None: MISSION_RESULT válido, também guardado em ``results``; None se o
                    prazo se esgotar.
            """
            agent = self.agent
            _, _, resource_id = assignment
            pending = getattr(self, "_pending_mission_result", None)
            self._pending_mission_result = None
            # O prazo real limita falhas de transporte; o movimento usa só tempo simulado.
            deadline = monotonic() + agent.receive_timeout * 10
            resends = agent.retransmit
            while True:
                received = pending if pending is not None else await self.receive_until(deadline)
                pending = None
                if received is None:
                    if not resends:
                        return None
                    # Reenvio: o mesmo ACCEPT serve de pergunta; o recurso repete confirmação e resultado.
                    resends -= 1
                    jid, accept, _ = assignment
                    await self.send_body(jid, accept, "accept-proposal", accept.payload["proposal_message_id"])
                    deadline = monotonic() + agent.receive_timeout * 10
                    continue
                incoming, result = received
                if self.result_matches_assignment(incoming, result, assignment, mission):
                    agent.results.append(result)
                    agent.record("MISSION_RESULT", resource_id=resource_id, payload=result.payload)
                    return result

        async def execute_task(self, mission, candidates):
            """Alocar a missão e esperar o resultado; só devolve resultados conclusivos.

            Devolve o resultado ``confirmed`` ou ``not_confirmed``. Com ``failed`` ou
            ``inconclusive``, o recurso sai dos candidatos e a missão repete-se com novo
            identificador, até ``max_attempts``. Uma reserva rejeitada também passa à
            tentativa seguinte, com os mesmos candidatos e a mesma missão. Nos restantes
            casos, incluindo o silêncio do recurso, devolve None e deixa o motivo em
            ``close_reason``.

            Args:
                mission (Mission): Missão a executar.
                candidates (Mapping[str, str]): ``resource_id`` de cada recurso candidato, por JID.

            Returns:
                Message | None: MISSION_RESULT ``confirmed`` ou ``not_confirmed``; None sem
                    resultado conclusivo.
            """
            agent = self.agent
            remaining = {bare(jid): resource for jid, resource in candidates.items()}
            rounds = 0
            for attempt in range(1, agent.max_attempts + 1):
                for wait in range(agent.queue_rounds + 1):
                    rounds += 1
                    self._busy, self._free_at = False, None
                    if agent.expire_unseen and not _recent_observations(agent.observation_feed):
                        # Prazo de validade: a janela do feed (várias leituras seguidas) ficou vazia.
                        agent.close_reason = "threat_expired"
                        return None
                    assignment, failure = await self.allocate(mission, remaining, rounds)
                    # Fila: recurso ocupado não é falha; esperar tempo simulado e voltar a pedir.
                    # shortcut: sem ordem de chegada nem prioridade; trocar por fila no recurso se for preciso.
                    if (assignment is not None or wait == agent.queue_rounds
                            or not (self._busy or failure == "reservation_rejected")):
                        break
                    # Relógio parado (ninguém em missão): o prazo real evita esperar para sempre.
                    until, limit = agent.simulated_time + QUEUE_INTERVAL_SECONDS, monotonic() + agent.receive_timeout
                    if agent.queue_until_free and (self._free_at or 0) > agent.simulated_time:
                        until = self._free_at  # o prazo real acima limita um busy_until absurdo
                    while agent.simulated_time < until and monotonic() < limit:
                        await asyncio.sleep(0.01)
                if assignment is None:
                    agent.close_reason = failure
                    if failure == "reservation_rejected" and attempt < agent.max_attempts:
                        continue
                    return None
                agent.transition(IncidentStatus.RESPONDING)
                running = mission.change_status(MissionStatus.RESERVED).change_status(MissionStatus.RUNNING)
                result = await self.mission_result(assignment, mission)
                if result is None:
                    # Silêncio não prova falha nem permite atribuir outra missão.
                    agent.close_reason = "mission_result_unknown"
                    agent.transition(IncidentStatus.ALLOCATING)
                    return None
                outcome = result.payload["outcome"]
                agent.missions.append(running.change_status(
                    MissionStatus.FAILED if outcome == "failed" else MissionStatus.DONE))
                if outcome in ("confirmed", "not_confirmed"):
                    return result
                agent.transition(IncidentStatus.ALLOCATING)
                remaining.pop(assignment[0])
                agent.close_reason = outcome
                mission = replace(mission, mission_id=f"{mission.mission_id}-retry-{attempt}")
                if not remaining:
                    break
            return None

        async def run(self):
            """Tratar um incidente do alerta ao fecho e marcar ``cycle_done``.

            Sem observações termina com ``no_alert``, sem criar incidente. Uma
            verificação confirmada pela patrulha gera uma segunda missão, de resposta,
            para os rangers.

            Overrides:
                isia.agents.sensor.SensorAgent.VerificationBehaviour.run
            """
            agent = self.agent
            observations = tuple(agent.observation_feed.recent())
            if not observations:
                agent.close_reason, agent.cycle_done = "no_alert", True
                return
            initial = observations[0]
            incident_id = f"incident-{initial.event_id}"
            agent.incident_observations = observations
            agent.incident_state = IncidentState(incident_id)
            agent.record("ALERT", observation_id=initial.event_id)
            if agent.neighbours:
                yields = await self.yields_to_neighbour(initial, incident_id)
                # A espera pelos vizinhos gasta tempo real e o relógio simulado pode ter andado:
                # a decisão usa a leitura atual, a mesma janela que o informador vai consultar.
                observations = () if yields else _recent_observations(agent.observation_feed)
                if not observations:
                    agent.close_reason = "duplicate_alert" if yields else "threat_expired"
                    agent.transition(IncidentStatus.CLOSED if yields else IncidentStatus.EXPIRED)
                    agent.record("INCIDENT_CLOSED", status=agent.incident_state.status.value,
                                 reason=agent.close_reason)
                    agent.cycle_done = True
                    return
                initial, agent.incident_observations = observations[0], observations
            agent.transition(IncidentStatus.VERIFYING)
            await super().run()
            agent.record("corroboration", decision=agent.decision)
            agent.transition(IncidentStatus.ASSESSING)
            mission = MissionRegistry().create_from_decision(
                Incident(incident_id, observations), agent.decision, priority=agent.severity_level)
            if mission is None:
                agent.transition(IncidentStatus.WATCHING)
                # MVP de uma janela: sem nova evidência, termina como expirado.
                agent.transition(IncidentStatus.EXPIRED)
                agent.close_reason = "insufficient_corroboration"
            else:
                agent.transition(IncidentStatus.ALLOCATING)
                candidates = agent.rangers if mission.task == RANGER_TASK else agent.patrols
                result = await self.execute_task(mission, candidates)
                if (mission.task == "verify_incident" and result is not None
                        and result.payload["outcome"] == "confirmed"):
                    agent.transition(IncidentStatus.ALLOCATING)
                    response = Mission(f"{mission.mission_id}-response", incident_id,
                                       RANGER_TASK, mission.target, RANGER_CAPABILITY, mission.priority)
                    result = await self.execute_task(response, agent.rangers)
                if result is None:
                    agent.transition(IncidentStatus.EXPIRED if agent.close_reason == "threat_expired"
                                     else IncidentStatus.UNRESOLVED)
                else:
                    agent.close_reason = result.payload["outcome"]
                    agent.transition(IncidentStatus.CLOSED)
            agent.record("INCIDENT_CLOSED", status=agent.incident_state.status.value,
                         reason=agent.close_reason)
            agent.cycle_done = True

    async def setup(self):
        """Registar o comportamento do incidente, filtrado pela ontologia.

        Overrides:
            isia.agents.sensor.SensorAgent.setup
        """
        self.behaviour = self.IncidentBehaviour()
        self.add_behaviour(self.behaviour, Template(metadata={"ontology": ONTOLOGY}))

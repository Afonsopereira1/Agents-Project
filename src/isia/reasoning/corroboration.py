"""Critérios locais e configuráveis para corroborar observações.

Por onde começar:

- `select_eligible_sources`: a quem pedir verificação.
- `aggregate_verification_responses`: juntar e classificar as respostas.
- `evaluate_reputation_corroboration`: score de suspeita ponderado pela reputação.
- `decide_preliminary_verification`: observar ou pedir patrulha.

A verificação de compatibilidade usa só as duas observações e os limites
configurados; nunca consulta a verdade do simulador nem os eventos reais.
"""

from collections.abc import Mapping
from math import fsum, hypot

from isia.communication.messages import Message, MessageType, model_from_dict, model_to_dict
from isia.domain.models import Observation
from isia.domain.models import Position
from isia.domain.validation import is_finite_number
from isia.simulation.scenario import SIGNALS, Source


def capability_supports_signal(capability: object, event_type: object) -> bool:
    """Reconhecer apenas correspondências modalidade-sinal definidas no simulador.

    Esta regra verifica a adequação *do tipo* de fonte, não prova que cada
    deteção individual tenha sensibilidade perfeita nem consulta ground_truth.
    Sinais desconhecidos não justificam ausência informativa por omissão.

    Args:
        capability (object): Modalidade declarada pela fonte (ex.: ``acoustic``).
        event_type (object): Tipo de sinal da hipótese.

    Returns:
        bool: ``True`` se o simulador associar essa modalidade a esse sinal.
    """
    return (
        isinstance(capability, str)
        and isinstance(event_type, str)
        and SIGNALS.get(capability) == event_type
    )


def are_observations_compatible(
    first: Observation,
    second: Observation,
    max_distance: float,
    max_time_difference: float,
) -> bool:
    """Dizer se duas observações podem referir-se à mesma ocorrência.

    Args:
        first (Observation): Primeira observação.
        second (Observation): Segunda observação.
        max_distance (float): Distância euclidiana máxima entre as posições (inclusiva).
        max_time_difference (float): Diferença máxima entre os instantes de observação
            (inclusiva), na mesma unidade de ``Observation.observed_at``.

    Returns:
        bool: ``True`` se os ``event_id`` forem diferentes e os dois limites forem
            cumpridos; senão ``False``.

    Raises:
        TypeError: Se uma observação ou um limite tiver um tipo inválido.
        ValueError: Se um limite for negativo ou não finito.
    """
    _validate_observation(first, "first")
    _validate_observation(second, "second")
    _validate_limit(max_distance, "max_distance")
    _validate_limit(max_time_difference, "max_time_difference")

    if first.event_id == second.event_id:
        return False

    time_difference = abs(first.observed_at - second.observed_at)

    return positions_within_distance(first.position, second.position, max_distance) and (
        time_difference <= max_time_difference
    )


def positions_within_distance(first: Position, second: Position, max_distance: float) -> bool:
    """Comparar posições sem deixar escapar overflow na conversão de inteiros.

    Args:
        first (Position): Primeira posição.
        second (Position): Segunda posição.
        max_distance (float): Distância euclidiana máxima (inclusiva).

    Returns:
        bool: ``True`` se a distância entre as posições não exceder ``max_distance``.

    Raises:
        TypeError: Se ``max_distance`` não for numérico.
        ValueError: Se ``max_distance`` for negativo ou não finito, ou se a distância
            exceder o intervalo numérico suportado.
    """
    _validate_limit(max_distance, "max_distance")
    try:
        distance = hypot(first.x - second.x, first.y - second.y)
    except OverflowError as error:
        raise ValueError("Position distance exceeds the supported numeric range.") from error
    return distance <= max_distance


def select_eligible_sources(
    observation: Observation,
    sensor_positions: Mapping[str, Position],
    source_profiles: Mapping[str, Source],
) -> tuple[str, ...]:
    """Devolver os sensores que podem ajudar a verificar a observação de forma independente.

    Uma fonte é elegível se:

    - tem posição e perfil ``Source`` conhecidos;
    - não é a fonte de ``observation``;
    - a observação está dentro do seu alcance de deteção (inclusive).

    A modalidade da fonte não é comparada com o tipo da observação, de
    propósito: fontes acústicas, visuais e humanas complementam-se.

    Usa só os metadados dos sensores; não consulta eventos do simulador, a
    verdade nem o histórico de outras fontes.

    Args:
        observation (Observation): Observação a verificar.
        sensor_positions (Mapping[str, Position]): Posição de cada sensor, por ID.
        source_profiles (Mapping[str, Source]): Perfil de cada fonte, com o alcance de
            deteção.

    Returns:
        tuple[str, ...]: IDs das fontes elegíveis, cada um uma vez, por ordem alfabética.

    Raises:
        TypeError: Se ``observation`` não for ``Observation``, se um dos mapas não for
            ``Mapping``, ou se uma posição ou perfil tiver o tipo errado.
    """
    if not isinstance(observation, Observation):
        raise TypeError("observation must be an Observation.")
    if not isinstance(sensor_positions, Mapping):
        raise TypeError("sensor_positions must be a mapping.")
    if not isinstance(source_profiles, Mapping):
        raise TypeError("source_profiles must be a mapping.")

    eligible = []
    for sensor_id in sorted(set(sensor_positions) & set(source_profiles)):
        if sensor_id == observation.source_id:
            continue

        position = sensor_positions[sensor_id]
        profile = source_profiles[sensor_id]
        if not isinstance(position, Position):
            raise TypeError("Each sensor position must be a Position.")
        if not isinstance(profile, Source):
            raise TypeError("Each source profile must be a Source.")

        if positions_within_distance(observation.position, position, profile.detection_range):
            eligible.append(sensor_id)

    return tuple(eligible)


def classify_verification_response(
    initial_observation: Observation,
    response: Message,
    max_distance: float,
    max_time_difference: float,
    *,
    incompatibility_rules: Mapping[str, object] | None = None,
    compatibility_rules: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Classificar a evidência de um ``VERIFY_RESPONSE`` já validado.

    Cada classificação exige:

    - **compatível:** uma observação com ``event_id`` e ``source_id``
      diferentes dos da inicial e que cumpra :func:`are_observations_compatible`;
    - **contradição:** a resposta declara ``evidence_relation == "contradictory"``,
      a hipótese devolvida corresponde à inicial e há uma regra de
      incompatibilidade dada pelo chamador; se a declaração vier com hipótese
      não correlacionada, nenhuma observação conta como compatível;
    - **tipos de evento diferentes:** uma regra de compatibilidade dada pelo chamador;
    - **ausência informativa:** uma declaração explícita e validada de não
      deteção e cobertura. Uma resposta vazia ou um timeout nunca bastam.

    Cada ``event_id`` é avaliado uma só vez. Não consulta o estado do
    simulador nem a verdade.

    Args:
        initial_observation (Observation): Observação que originou o pedido.
        response (Message): ``VERIFY_RESPONSE`` a classificar.
        max_distance (float): Distância máxima para observações compatíveis (inclusiva).
        max_time_difference (float): Diferença temporal máxima (inclusiva).
        incompatibility_rules (Mapping[str, object] | None): Tipos de evento que
            contradizem cada tipo; ``None`` desativa contradições.
        compatibility_rules (Mapping[str, object] | None): Tipos de evento, além do
            próprio, compatíveis com cada tipo.

    Returns:
        dict[str, object]: ``classification`` (``compatible``, ``contradictory``,
            ``informative_absence``, ``inconclusive`` ou ``no_data``) e os
            ``observation_ids`` usados para a obter, sem repetições; em evidência mista,
            também ``compatible_observation_ids`` e ``contradictory_observation_ids``.

    Raises:
        TypeError: Se ``initial_observation`` ou ``response`` tiverem o tipo errado, ou
            se um limite ou as regras forem de tipo inválido.
        ValueError: Se um limite for negativo ou não finito, se a resposta for inválida
            ou se as regras contiverem strings vazias.
    """
    _validate_observation(initial_observation, "initial_observation")
    _validate_limit(max_distance, "max_distance")
    _validate_limit(max_time_difference, "max_time_difference")
    observations, status = _observations_from_response(response)

    if status == "no_data":
        return {"classification": "no_data", "observation_ids": ()}

    if status == "informative_absence":
        if _informative_absence_is_valid(initial_observation, response):
            return {
                "classification": "informative_absence",
                "observation_ids": (),
            }
        return {"classification": "inconclusive", "observation_ids": ()}

    unique_observations = []
    seen_event_ids = set()
    for observation in observations:
        if observation.event_id in seen_event_ids:
            continue
        seen_event_ids.add(observation.event_id)
        if (
            observation.event_id != initial_observation.event_id
            and observation.source_id != initial_observation.source_id
        ):
            unique_observations.append(observation)

    incompatible_types = _configured_types(
        initial_observation.event_type, incompatibility_rules, "incompatibility"
    )
    compatible_types = {initial_observation.event_type}
    compatible_types.update(
        _configured_types(initial_observation.event_type, compatibility_rules, "compatibility")
    )
    # A declaração de contradição refere-se à resposta; cada observação
    # continua a ser classificada pelo seu próprio tipo e pelas regras locais.
    contradictory_declaration = (
        response.payload.get("evidence_relation") == "contradictory"
    )
    explicit_contradiction = contradictory_declaration and _hypothesis_is_correlated(
        initial_observation, response
    )
    contradictory = [
        observation
        for observation in unique_observations
        if explicit_contradiction
        and observation.event_type in incompatible_types
        and are_observations_compatible(
            initial_observation,
            observation,
            max_distance,
            max_time_difference,
        )
    ]
    contradictory_ids = {observation.event_id for observation in contradictory}
    compatible = [
        observation
        for observation in unique_observations
        if observation.event_id not in contradictory_ids
        and (not contradictory_declaration or explicit_contradiction)
        and observation.event_type in compatible_types
        and are_observations_compatible(
            initial_observation,
            observation,
            max_distance,
            max_time_difference,
        )
    ]
    if compatible and contradictory:
        return {
            "classification": "inconclusive",
            "observation_ids": tuple(
                observation.event_id
                for observation in (*compatible, *contradictory)
            ),
            "compatible_observation_ids": tuple(
                observation.event_id for observation in compatible
            ),
            "contradictory_observation_ids": tuple(
                observation.event_id for observation in contradictory
            ),
        }
    if contradictory:
        return {
            "classification": "contradictory",
            "observation_ids": tuple(
                observation.event_id for observation in contradictory
            ),
        }
    if compatible:
        return {
            "classification": "compatible",
            "observation_ids": tuple(observation.event_id for observation in compatible),
        }

    return {
        "classification": "inconclusive",
        "observation_ids": tuple(observation.event_id for observation in unique_observations),
    }


def aggregate_verification_responses(
    initial_observation: Observation,
    responses,
    conversation_id: str,
    request_message_id: str,
    max_distance: float,
    max_time_difference: float,
    *,
    incompatibility_rules: Mapping[str, object] | None = None,
    compatibility_rules: Mapping[str, object] | None = None,
    expected_incident_id: str | None = None,
) -> dict[str, object]:
    """Juntar as várias respostas a um pedido de verificação.

    Só aceita mensagens ``VERIFY_RESPONSE`` da conversa esperada e que se
    refiram ao pedido esperado. Cada mensagem é processada uma vez (por
    ``message_id``) e cada observação contada uma vez (por ``event_id``). As
    ``source_ids`` e as fontes compatíveis vêm das próprias observações, nunca
    do remetente nem do ``source_id`` da resposta; só a ausência informativa
    (e, por isso, ``coverage_source_ids``) usa o ``source_id`` da resposta.
    Várias observações da mesma fonte contam como uma só fonte compatível.

    Args:
        initial_observation (Observation): Observação que originou o pedido.
        responses (Iterable[Message]): ``VERIFY_RESPONSE`` recebidas.
        conversation_id (str): Conversa do pedido de verificação.
        request_message_id (str): ID do ``VERIFY_REQUEST`` a que as respostas respondem.
        max_distance (float): Distância máxima para observações compatíveis (inclusiva).
        max_time_difference (float): Diferença temporal máxima (inclusiva).
        incompatibility_rules (Mapping[str, object] | None): Tipos de evento que
            contradizem cada tipo.
        compatibility_rules (Mapping[str, object] | None): Tipos de evento, além do
            próprio, compatíveis com cada tipo.
        expected_incident_id (str | None): Incidente esperado; ``None`` não o verifica.

    Returns:
        dict[str, object]: ``classification``, as ``observations`` e
            ``observation_ids`` independentes, os IDs compatíveis, contraditórios e em
            conflito, os ``source_ids`` distintos, ``compatible_source_ids``,
            ``compatible_source_count``, ``informative_absence_source_ids`` e
            ``coverage_source_ids``.

    Raises:
        TypeError: Se ``initial_observation`` não for ``Observation``, se alguma resposta
            não for ``Message``, ou se um limite ou as regras tiverem o tipo errado.
        ValueError: Se um identificador estiver vazio, um limite for negativo ou não
            finito, ou se uma resposta for inválida ou pertencer a outra conversa,
            pedido ou incidente.
    """
    _validate_observation(initial_observation, "initial_observation")
    _validate_reference(conversation_id, "conversation_id")
    _validate_reference(request_message_id, "request_message_id")
    if expected_incident_id is not None:
        _validate_reference(expected_incident_id, "expected_incident_id")
    _validate_limit(max_distance, "max_distance")
    _validate_limit(max_time_difference, "max_time_difference")

    seen_message_ids = set()
    observation_variants = {}
    observation_interpretations = {}
    compatible_ids = set()
    contradictory_ids = set()
    informative_absence_source_ids = set()
    saw_observation_response = False
    saw_no_data = False

    for response in responses:
        if not isinstance(response, Message):
            raise TypeError("Each response must be a Message.")
        observations, status = _observations_from_response(response)
        if response.conversation_id != conversation_id:
            raise ValueError("VERIFY_RESPONSE belongs to another conversation.")
        if response.payload["request_message_id"] != request_message_id:
            raise ValueError("VERIFY_RESPONSE refers to another request.")
        if expected_incident_id is not None and response.incident_id != expected_incident_id:
            raise ValueError("VERIFY_RESPONSE belongs to another incident.")
        if response.message_id in seen_message_ids:
            continue
        seen_message_ids.add(response.message_id)

        result = classify_verification_response(
            initial_observation,
            response,
            max_distance,
            max_time_difference,
            incompatibility_rules=incompatibility_rules,
            compatibility_rules=compatibility_rules,
        )
        if status == "no_data":
            saw_no_data = True
            continue
        if status == "informative_absence":
            if result["classification"] == "informative_absence":
                if response.source_id:
                    informative_absence_source_ids.add(response.source_id)
            continue
        saw_observation_response = True

        for observation in observations:
            if (
                observation.event_id == initial_observation.event_id
                or observation.source_id == initial_observation.source_id
            ):
                continue
            variants = observation_variants.setdefault(observation.event_id, [])
            if observation not in variants:
                variants.append(observation)

        # Os IDs de evidência mista são preservados mesmo quando a
        # classificação individual é inconclusive.
        compatible_ids.update(result.get("compatible_observation_ids", ()))
        contradictory_ids.update(result.get("contradictory_observation_ids", ()))
        if result["classification"] == "compatible":
            compatible_ids.update(result["observation_ids"])
        elif result["classification"] == "contradictory":
            contradictory_ids.update(result["observation_ids"])

        for observation_id in result.get("compatible_observation_ids", ()):
            observation_interpretations.setdefault(observation_id, set()).add(
                "compatible"
            )
        for observation_id in result.get("contradictory_observation_ids", ()):
            observation_interpretations.setdefault(observation_id, set()).add(
                "contradictory"
            )
        if result["classification"] == "compatible":
            for observation_id in result["observation_ids"]:
                observation_interpretations.setdefault(observation_id, set()).add(
                    "compatible"
                )
        elif result["classification"] == "contradictory":
            for observation_id in result["observation_ids"]:
                observation_interpretations.setdefault(observation_id, set()).add(
                    "contradictory"
                )

    unique_observations = {
        event_id: min(variants, key=_observation_sort_key)
        for event_id, variants in observation_variants.items()
    }
    conflicted_ids = {
        event_id
        for event_id, variants in observation_variants.items()
        if len(variants) > 1
        or len(observation_interpretations.get(event_id, set())) > 1
    }
    compatible_ids.difference_update(conflicted_ids)
    contradictory_ids.difference_update(conflicted_ids)
    compatible_ids.intersection_update(unique_observations)
    contradictory_ids.intersection_update(unique_observations)
    source_ids = {
        observation.source_id
        for variants in observation_variants.values()
        for observation in variants
    }
    compatible_source_ids = {
        unique_observations[event_id].source_id for event_id in compatible_ids
    }

    if conflicted_ids or (compatible_ids and contradictory_ids):
        classification = "inconclusive"
    elif compatible_ids:
        classification = "compatible"
    elif contradictory_ids:
        classification = "contradictory"
    elif informative_absence_source_ids:
        classification = "informative_absence"
    elif saw_observation_response:
        classification = "inconclusive"
    elif saw_no_data or not seen_message_ids:
        classification = "no_data"
    else:  # Defensive fallback for future response statuses.
        classification = "inconclusive"

    return {
        "classification": classification,
        "observations": tuple(model_to_dict(unique_observations[key]) for key in sorted(unique_observations)),
        "observation_ids": tuple(sorted(unique_observations)),
        "compatible_observation_ids": tuple(sorted(compatible_ids)),
        "contradictory_observation_ids": tuple(sorted(contradictory_ids)),
        "conflicted_observation_ids": tuple(sorted(conflicted_ids)),
        "source_ids": tuple(sorted(source_ids)),
        "compatible_source_ids": tuple(sorted(compatible_source_ids)),
        "compatible_source_count": len(compatible_source_ids),
        "informative_absence_source_ids": tuple(
            sorted(informative_absence_source_ids)
        ),
        "coverage_source_ids": tuple(
            sorted(source_ids | informative_absence_source_ids)
        ),
    }


def validate_source_profiles(source_profiles: Mapping[str, Mapping[str, str]]) -> None:
    """Exigir exatamente ``modality`` e ``correlation_group`` em cada perfil.

    Args:
        source_profiles (Mapping[str, Mapping[str, str]]): Perfil de cada fonte, por ID.

    Raises:
        ValueError: Se um ID ou valor não for uma string não vazia, ou se um perfil não
            tiver exatamente as duas chaves.
    """
    for source_id, profile in source_profiles.items():
        _validate_reference(source_id, "source_id")
        if set(profile) != {"modality", "correlation_group"}:
            raise ValueError("Cada fonte requer modality e correlation_group.")
        for value in profile.values():
            _validate_reference(value, "source profile")


def evaluate_reputation_corroboration(
    initial_observation: Observation,
    aggregate_summary: Mapping[str, object],
    eligible_source_ids,
    reputation_scores: Mapping[str, float],
    source_profiles: Mapping[str, Mapping[str, str]],
    max_distance: float,
    max_time_difference: float,
    *,
    default_reputation: float = 0.5,
) -> dict[str, object]:
    """Calcular o score heurístico de suspeita, ponderado pela reputação.

    O score nunca é uma probabilidade calibrada.
    Peso = reputação × confiança declarada × proximidade temporal × espacial.
    Cada grupo de fontes correlacionadas contribui no máximo uma vez por sinal
    (positivo/negativo). Metadados desconhecidos partilham um grupo conservador.
    Ausência informativa reduz apoio; timeout/no_data não o reduz.

    Args:
        initial_observation (Observation): Observação que originou o pedido.
        aggregate_summary (Mapping[str, object]): Resultado de
            :func:`aggregate_verification_responses`.
        eligible_source_ids (Iterable[str]): Fontes elegíveis, de
            :func:`select_eligible_sources`.
        reputation_scores (Mapping[str, float]): Reputação de cada fonte, entre 0 e 1.
        source_profiles (Mapping[str, Mapping[str, str]]): ``modality`` e
            ``correlation_group`` de cada fonte.
        max_distance (float): Distância máxima para evidência compatível (inclusiva).
        max_time_difference (float): Diferença temporal máxima (inclusiva).
        default_reputation (float): Reputação das fontes sem score, entre 0 e 1.

    Returns:
        dict[str, object]: Indicadores de
            :func:`evaluate_preliminary_corroboration` acrescidos de
            ``suspicion_score`` (entre 0 e 1), ``support``, ``opposition``,
            ``diversity_factor``, ``supporting_group_count``, ``modalities``,
            ``conflicting_evidence`` e os ``factors`` de cada evidência.

    Raises:
        TypeError: Se ``initial_observation`` não for ``Observation``, se
            ``aggregate_summary`` não for ``Mapping``, se um limite tiver o tipo errado
            ou se ``eligible_source_ids`` não for iterável.
        ValueError: Se um limite for negativo ou não finito, uma reputação estiver fora
            de [0, 1], se os perfis ou os IDs elegíveis forem inválidos, ou se uma
            observação do resumo for inválida.
    """
    _validate_observation(initial_observation, "initial_observation")
    _validate_limit(max_distance, "max_distance")
    _validate_limit(max_time_difference, "max_time_difference")
    for value in (default_reputation, *reputation_scores.values()):
        if not is_finite_number(value) or not 0 <= value <= 1:
            raise ValueError("Reputação deve estar entre 0 e 1.")
    validate_source_profiles(source_profiles)
    eligible = set(_unique_identifiers(eligible_source_ids, "eligible_source_ids"))
    evaluation = evaluate_preliminary_corroboration(aggregate_summary, eligible)
    positive = set(aggregate_summary.get("compatible_observation_ids", ()))
    negative = set(aggregate_summary.get("contradictory_observation_ids", ()))
    conflicted = set(aggregate_summary.get("conflicted_observation_ids", ()))
    factors = []
    groups = {}

    def add(source_id, event_id, relation, confidence, temporal, spatial):
        """Registar um fator de evidência e atualizar o grupo de correlação da fonte.

        Cada grupo guarda apenas o maior peso por relação. A modalidade só conta
        para a diversidade com apoio positivo, peso não nulo e modalidade conhecida.
        """
        profile = source_profiles.get(source_id, {})
        group = profile.get("correlation_group", "unknown")
        modality = profile.get("modality", "unknown")
        reputation = reputation_scores.get(source_id, default_reputation)
        weight = reputation * confidence * temporal * spatial
        factors.append({
            "source_id": source_id, "event_id": event_id, "relation": relation,
            "reputation": reputation, "confidence": confidence,
            "temporal_factor": temporal, "spatial_factor": spatial,
            "modality": modality, "correlation_group": group, "weight": weight,
        })
        entry = groups.setdefault(group, {"positive": 0.0, "negative": 0.0, "modalities": set()})
        entry[relation] = max(entry[relation], weight)
        if relation == "positive" and weight > 0 and modality != "unknown":
            entry["modalities"].add(modality)

    add(initial_observation.source_id, initial_observation.event_id, "positive",
        initial_observation.confidence_score, 1.0, 1.0)
    for raw in aggregate_summary.get("observations", ()):
        observation = model_from_dict(raw, Observation)
        event_id = observation.event_id
        if (observation.source_id not in eligible or event_id in conflicted
                or observation.source_id == initial_observation.source_id):
            continue
        if event_id not in positive | negative or not are_observations_compatible(
            initial_observation, observation, max_distance, max_time_difference
        ):
            continue
        distance = hypot(initial_observation.position.x - observation.position.x,
                         initial_observation.position.y - observation.position.y)
        delta = abs(initial_observation.observed_at - observation.observed_at)
        temporal = 1 / (1 + delta / max_time_difference) if max_time_difference else 1.0
        spatial = 1 / (1 + distance / max_distance) if max_distance else 1.0
        add(observation.source_id, event_id, "negative" if event_id in negative else "positive",
            observation.confidence_score, temporal, spatial)
    for source_id in sorted(set(aggregate_summary.get("informative_absence_source_ids", ())) & eligible):
        if source_id != initial_observation.source_id:
            add(source_id, None, "negative", 1.0, 1.0, 1.0)

    supporting = [entry for entry in groups.values() if entry["positive"] > entry["negative"]]
    modalities = set().union(*(entry["modalities"] for entry in supporting))
    diversity = 0.5 + 0.25 * min(2, len(modalities))
    support = fsum(entry["positive"] for entry in groups.values())
    opposition = fsum(entry["negative"] for entry in groups.values())
    # ponytail: máximo por grupo é uma heurística; substituir só após medir dependências.
    # Duas unidades de apoio líquido saturam a escala. Evidência de peso zero
    # não dilui apoio existente só por acrescentar outro grupo.
    score = max(0.0, min(1.0, (support - opposition) / 2)) * diversity
    evaluation.update({
        "suspicion_score": score, "score_kind": "heuristic_not_probability",
        "support": support, "opposition": opposition, "diversity_factor": diversity,
        "supporting_group_count": len(supporting), "modalities": tuple(sorted(modalities)),
        "conflicting_evidence": bool(conflicted) or (support > 0 and opposition > 0),
        "factors": tuple(sorted(factors, key=lambda item: (item["source_id"], item["event_id"] or ""))),
        "group_count": len(groups),
        "max_distance": max_distance, "max_time_difference": max_time_difference,
    })
    return evaluation


def _observation_sort_key(observation: Observation) -> tuple:
    """Devolver uma chave determinística para escolher a variante canónica de cada ``event_id``."""
    return (
        observation.source_id,
        observation.event_type,
        observation.position.x,
        observation.position.y,
        observation.observed_at,
        observation.confidence_score,
        observation.intensity_score is not None,
        observation.intensity_score or 0.0,
    )


def evaluate_preliminary_corroboration(
    aggregate_summary: Mapping[str, object],
    eligible_source_ids,
) -> dict[str, object]:
    """Calcular os indicadores de cobertura a partir do resumo agregado.

    ``eligible_source_ids`` tem de vir de :func:`select_eligible_sources`. Só
    conta as fontes, sem repetições, que já estão no resumo:

    - **score preliminar** = fontes elegíveis compatíveis / fontes elegíveis;
    - **cobertura de informação** = fontes elegíveis com observações ou ausência
      informativa válida / fontes elegíveis.

    São indicadores descritivos, não probabilidades calibradas: fontes
    diferentes podem partilhar hardware, local, software ou pontos cegos, por
    isso não são necessariamente independentes.

    Args:
        aggregate_summary (Mapping[str, object]): Resultado de
            :func:`aggregate_verification_responses`.
        eligible_source_ids (Iterable[str]): Fontes elegíveis para a observação.

    Returns:
        dict[str, object]: ``classification``, ``compatible_observation_ids``,
            ``eligible_source_count``, IDs e contagens das fontes compatíveis e
            observadas, ``preliminary_score`` e ``information_coverage`` (ambos
            ``None`` se não houver fontes elegíveis).

    Raises:
        TypeError: Se ``aggregate_summary`` não for ``Mapping`` ou um conjunto de IDs
            não for iterável.
        ValueError: Se algum ID não for uma string não vazia.
    """
    if not isinstance(aggregate_summary, Mapping):
        raise TypeError("aggregate_summary must be a mapping.")
    eligible = _unique_identifiers(eligible_source_ids, "eligible_source_ids")
    eligible_set = set(eligible)

    compatible_source_ids = _summary_identifiers(
        aggregate_summary, "compatible_source_ids"
    ) & eligible_set
    observed_source_ids = (
        _summary_identifiers(
            aggregate_summary,
            "coverage_source_ids",
        )
        or _summary_identifiers(aggregate_summary, "source_ids")
    ) & eligible_set

    eligible_count = len(eligible_set)
    if not eligible_count:
        score = None
        coverage = None
        compatible_source_ids = set()
        observed_source_ids = set()
    else:
        score = len(compatible_source_ids) / eligible_count
        coverage = len(observed_source_ids) / eligible_count

    return {
        "classification": aggregate_summary.get("classification"),
        "compatible_observation_ids": tuple(sorted(_summary_identifiers(
            aggregate_summary, "compatible_observation_ids"
        ))),
        "eligible_source_count": eligible_count,
        "compatible_source_ids": tuple(sorted(compatible_source_ids)),
        "compatible_source_count": len(compatible_source_ids),
        "observed_source_ids": tuple(sorted(observed_source_ids)),
        "observed_source_count": len(observed_source_ids),
        "preliminary_score": score,
        "information_coverage": coverage,
    }


def decide_preliminary_verification(
    evaluation_summary: Mapping[str, object],
    minimum_compatible_sources: int,
) -> dict[str, object]:
    """Escolher entre continuar a observar e pedir verificação por patrulha.

    Regra operacional explícita: pede verificação quando o resumo atinge
    ``minimum_compatible_sources`` fontes compatíveis distintas e há fontes
    elegíveis; senão continua a observar. O limiar é um parâmetro de engenharia dado pelo chamador, não
    uma estimativa validada da probabilidade de caça furtiva.

    Não processa mensagens nem observações: recebe o resultado de
    :func:`evaluate_preliminary_corroboration`, que já tirou as repetições.

    Args:
        evaluation_summary (Mapping[str, object]): Resultado de
            :func:`evaluate_preliminary_corroboration`.
        minimum_compatible_sources (int): Fontes compatíveis distintas necessárias para
            pedir patrulha; inteiro positivo.

    Returns:
        dict[str, object]: ``decision`` (``observe`` ou ``request_mobile_verification``),
            ``reason`` e os indicadores do resumo usados na decisão.

    Raises:
        TypeError: Se ``evaluation_summary`` não for ``Mapping``, se
            ``minimum_compatible_sources`` não for inteiro, ou se um conjunto de IDs não
            for iterável.
        ValueError: Se ``minimum_compatible_sources`` não for positivo, se uma contagem
            não for um inteiro não negativo, ou se algum ID for inválido.
    """
    if not isinstance(evaluation_summary, Mapping):
        raise TypeError("evaluation_summary must be a mapping.")
    if isinstance(minimum_compatible_sources, bool) or not isinstance(
        minimum_compatible_sources, int
    ):
        raise TypeError("minimum_compatible_sources must be a positive integer.")
    if minimum_compatible_sources <= 0:
        raise ValueError("minimum_compatible_sources must be a positive integer.")

    eligible_count = _nonnegative_count(
        evaluation_summary.get("eligible_source_count", 0),
        "eligible_source_count",
    )
    observed_count = _nonnegative_count(
        evaluation_summary.get("observed_source_count", 0),
        "observed_source_count",
    )
    compatible_source_ids = _summary_identifiers(
        evaluation_summary, "compatible_source_ids"
    )
    compatible_count = len(compatible_source_ids)

    if compatible_count >= minimum_compatible_sources and eligible_count > 0:
        decision = "request_mobile_verification"
        reason = "compatible_source_threshold_reached"
    elif eligible_count == 0:
        decision = "observe"
        reason = "no_eligible_sources"
    elif observed_count == 0:
        decision = "observe"
        reason = "no_information"
    elif compatible_count == 0:
        decision = "observe"
        reason = "no_compatible_evidence"
    else:
        decision = "observe"
        reason = "insufficient_compatible_evidence"

    return {
        "decision": decision,
        "reason": reason,
        "compatible_observation_ids": tuple(
            sorted(
                _summary_identifiers(
                    evaluation_summary, "compatible_observation_ids"
                )
            )
        ),
        "compatible_source_ids": tuple(sorted(compatible_source_ids)),
        "compatible_source_count": compatible_count,
        "eligible_source_count": eligible_count,
        "observed_source_count": observed_count,
        "preliminary_score": evaluation_summary.get("preliminary_score"),
        "information_coverage": evaluation_summary.get("information_coverage"),
        "minimum_compatible_sources": minimum_compatible_sources,
    }


def _observations_from_response(response: Message) -> tuple[tuple[Observation, ...], str]:
    """Validar um ``VERIFY_RESPONSE`` e devolver as suas observações e o ``status``.

    Raises:
        TypeError: Se ``response`` não for ``Message``.
        ValueError: Se o tipo, o payload, o estado ou alguma observação forem inválidos,
            se o estado não for coerente com a lista de observações, ou se uma
            observação ou o fim do intervalo de ausência forem posteriores à emissão
            da resposta.
    """
    if not isinstance(response, Message):
        raise TypeError("response must be a Message.")
    if response.message_type is not MessageType.VERIFY_RESPONSE:
        raise ValueError("response must be a VERIFY_RESPONSE message.")

    payload = response.payload
    if not isinstance(payload, dict):
        raise ValueError("VERIFY_RESPONSE payload must be an object.")
    request_message_id = payload.get("request_message_id")
    if not isinstance(request_message_id, str) or not request_message_id.strip():
        raise ValueError("VERIFY_RESPONSE must identify its request message.")

    status = payload.get("status")
    if status not in {
        "observations_available",
        "no_data",
        "informative_absence",
    }:
        raise ValueError("VERIFY_RESPONSE status is invalid.")
    raw_observations = payload.get("observations")
    if not isinstance(raw_observations, list):
        raise ValueError("VERIFY_RESPONSE observations must be a list.")
    if status in {"no_data", "informative_absence"} and raw_observations:
        raise ValueError("A no_data response cannot contain observations.")
    if status == "observations_available" and not raw_observations:
        raise ValueError("An observations_available response must contain observations.")
    if status == "informative_absence":
        absence = payload.get("absence")
        observed_until = absence.get("observed_until") if isinstance(absence, Mapping) else None
        if is_finite_number(observed_until) and observed_until > response.created_at:
            raise ValueError("VERIFY_RESPONSE cannot claim a future observation interval.")

    observations = []
    for raw_observation in raw_observations:
        try:
            observation = model_from_dict(raw_observation, Observation)
        except (TypeError, ValueError, KeyError) as error:
            raise ValueError("VERIFY_RESPONSE contains an invalid observation.") from error
        if observation.observed_at > response.created_at:
            raise ValueError("VERIFY_RESPONSE cannot contain a future observation.")
        observations.append(observation)
    return tuple(observations), status


def build_observation_hypothesis(observation: Observation) -> dict[str, object]:
    """Construir a hipótese opcional enviada no pedido (compatível com o contrato anterior).

    Args:
        observation (Observation): Observação que define a hipótese.

    Returns:
        dict[str, object]: ``hypothesis_id``, ``event_type``, ``position`` e o intervalo
            ``valid_from``/``valid_until`` (ambos no instante da observação).

    Raises:
        TypeError: Se ``observation`` não for ``Observation``.
    """
    _validate_observation(observation, "observation")
    return {
        "hypothesis_id": f"hypothesis-{observation.event_id}",
        "event_type": observation.event_type,
        "position": {"x": observation.position.x, "y": observation.position.y},
        "valid_from": observation.observed_at,
        "valid_until": observation.observed_at,
    }


def _configured_types(event_type: str, rules: Mapping[str, object] | None, name: str) -> set[str]:
    """Devolver os tipos que as regras do chamador associam a ``event_type``.

    ``name`` só entra nas mensagens de erro.

    Raises:
        TypeError: Se ``rules`` não for ``Mapping`` ou a regra de ``event_type`` não for
            iterável.
        ValueError: Se a regra contiver valores que não sejam strings não vazias.
    """
    if rules is None:
        return set()
    if not isinstance(rules, Mapping):
        raise TypeError(f"{name}_rules must be a mapping.")
    values = rules.get(event_type, ())
    if isinstance(values, str):
        values = (values,)
    try:
        values = tuple(values)
    except TypeError as error:
        raise TypeError(f"Each {name} rule must be iterable.") from error
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{name.capitalize()} rules must contain non-empty strings.")
    return set(values)


def _hypothesis_is_correlated(
    initial_observation: Observation,
    response: Message,
) -> bool:
    """Verificar se a hipótese ecoada na resposta corresponde à observação inicial.

    Exige ID não vazio, o mesmo tipo de evento, a mesma posição e um intervalo
    de validade finito que contenha o instante da observação. Hipótese ausente
    ou malformada devolve ``False`` em vez de levantar erro.
    """
    hypothesis = response.payload.get("hypothesis")
    if not isinstance(hypothesis, Mapping):
        return False
    try:
        hypothesis_id = hypothesis["hypothesis_id"]
        event_type = hypothesis["event_type"]
        position = model_from_dict(hypothesis["position"], Position)
        valid_from = hypothesis["valid_from"]
        valid_until = hypothesis["valid_until"]
    except (KeyError, TypeError, ValueError):
        return False
    return (
        isinstance(hypothesis_id, str)
        and bool(hypothesis_id.strip())
        and event_type == initial_observation.event_type
        and position == initial_observation.position
        and is_finite_number(valid_from)
        and is_finite_number(valid_until)
        and valid_from <= initial_observation.observed_at <= valid_until
        and valid_from <= valid_until
    )


def _informative_absence_is_valid(
    initial_observation: Observation,
    response: Message,
) -> bool:
    """Verificar se uma ausência declarada conta como evidência negativa.

    Exige fonte identificada, hipótese correlacionada e referida pela ausência,
    não-deteção explícita, capacidade adequada ao sinal e validada, oportunidade
    confirmada, intervalo de observação que cubra o da hipótese e posição da
    hipótese dentro do raio de cobertura. Campos em falta devolvem ``False``.
    """
    hypothesis = response.payload.get("hypothesis")
    absence = response.payload.get("absence")
    if not isinstance(hypothesis, Mapping) or not isinstance(absence, Mapping):
        return False
    if not isinstance(response.source_id, str) or not response.source_id.strip():
        return False
    if not _hypothesis_is_correlated(initial_observation, response):
        return False
    try:
        coverage = absence["coverage"]
        coverage_position = model_from_dict(coverage["position"], Position)
        radius = coverage["radius"]
        observed_from = absence["observed_from"]
        observed_until = absence["observed_until"]
        capability = coverage["capability"]
        capability_validated = coverage["capability_validated"]
        opportunity_confirmed = coverage["opportunity_confirmed"]
        hypothesis_id = absence["hypothesis_id"]
        declared_non_detection = absence["declared_non_detection"]
        hypothesis_from = hypothesis["valid_from"]
        hypothesis_until = hypothesis["valid_until"]
        hypothesis_position = model_from_dict(hypothesis["position"], Position)
    except (KeyError, TypeError, ValueError):
        return False
    if (
        not isinstance(coverage, Mapping)
        or not isinstance(hypothesis_id, str)
        or not hypothesis_id.strip()
        or hypothesis_id != hypothesis.get("hypothesis_id")
        or declared_non_detection is not True
        or capability_validated is not True
        or opportunity_confirmed is not True
        or not capability_supports_signal(capability, hypothesis.get("event_type"))
        or not is_finite_number(radius)
        or radius < 0
        or not is_finite_number(observed_from)
        or not is_finite_number(observed_until)
        or observed_from > observed_until
        or observed_from > hypothesis_from
        or observed_until < hypothesis_until
    ):
        return False
    return positions_within_distance(coverage_position, hypothesis_position, radius)


def _validate_reference(value: str, name: str) -> None:
    """Exigir que ``value`` seja uma string não vazia.

    Raises:
        ValueError: Se ``value`` não for uma string não vazia.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")


def _unique_identifiers(values, name: str) -> tuple[str, ...]:
    """Devolver os identificadores sem duplicados, por ordem lexicográfica.

    Raises:
        TypeError: Se ``values`` não for iterável.
        ValueError: Se algum elemento não for uma string não vazia.
    """
    try:
        identifiers = tuple(values)
    except TypeError as error:
        raise TypeError(f"{name} must be iterable.") from error
    if any(not isinstance(value, str) or not value.strip() for value in identifiers):
        raise ValueError(f"{name} must contain non-empty strings.")
    return tuple(sorted(set(identifiers)))


def _summary_identifiers(summary: Mapping[str, object], name: str) -> set[str]:
    """Ler ``name`` do sumário como conjunto de IDs validados; vazio se faltar.

    Raises:
        TypeError: Se o valor não for iterável.
        ValueError: Se algum ID não for uma string não vazia.
    """
    values = summary.get(name, ())
    identifiers = _unique_identifiers(values, name)
    return set(identifiers)


def _nonnegative_count(value: object, name: str) -> int:
    """Devolver ``value`` se for inteiro não negativo.

    Raises:
        ValueError: Se ``value`` não for um inteiro não negativo (``bool`` não conta).
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer.")
    return value


def _validate_observation(observation: Observation, name: str) -> None:
    """Exigir que ``observation`` seja uma ``Observation``.

    Raises:
        TypeError: Se ``observation`` não for ``Observation``.
    """
    if not isinstance(observation, Observation):
        raise TypeError(f"{name} must be an Observation.")


def _validate_limit(value: float, name: str) -> None:
    """Exigir número finito e não negativo.

    Raises:
        TypeError: Se ``value`` não for ``int`` ou ``float`` (``bool`` não conta).
        ValueError: Se ``value`` for negativo ou não finito.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite non-negative number.")
    if not is_finite_number(value) or value < 0:
        raise ValueError(f"{name} must be a finite non-negative number.")

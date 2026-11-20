"""Frequência observada por intervalo de score, apenas na camada de avaliação.

O ``suspicion_score`` é heurístico. Estas tabelas descrevem a frequência de
ameaças entre as execuções com score disponível; não o transformam numa
probabilidade calibrada. A cobertura separada inclui as execuções sem score.
"""

from collections import defaultdict

from isia.domain.validation import is_finite_number


INTERVALS = ((0.0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1.0))


def initial_score(report):
    """Ler o score antes da missão no histórico imutável da verificação.

    O campo de topo ``decision`` pode já conter a decisão após uma missão.
    No MVP de janela única existe no máximo uma avaliação inicial por run.
    Históricos com várias avaliações exigem definir outra unidade estatística;
    rejeitá-los evita escolher silenciosamente um score favorável.

    Args:
        report (dict[str, Any]): Relatório de uma execução de ``run_mvp``.

    Returns:
        float | None: ``suspicion_score`` em [0, 1], ou ``None`` se não houve avaliação inicial.

    Raises:
        ValueError: Se ``verification`` estiver malformado, houver mais de uma avaliação
            ou o score não for um número finito em [0, 1].
    """
    history = report.get("verification")
    if not isinstance(history, dict):
        raise ValueError("O relatório deve conter verification como dicionário.")
    policies = []
    for conversation in history.values():
        if not isinstance(conversation, dict):
            raise ValueError("Cada conversa de verification deve ser um dicionário.")
        for entry in conversation.values():
            if not isinstance(entry, dict):
                raise ValueError("Cada registo de verification deve ser um dicionário.")
            policy = entry.get("response_policy")
            if policy is not None:
                if not isinstance(policy, dict):
                    raise ValueError("response_policy deve ser dicionário ou None.")
                policies.append(policy)
    if len(policies) > 1:
        raise ValueError("Vários scores iniciais: a calibração exige uma avaliação por execução.")
    if not policies:
        return None
    policy = policies[0]
    score = policy.get("suspicion_score")
    if not is_finite_number(score) or not 0 <= score <= 1:
        raise ValueError("suspicion_score deve ser um número finito entre 0 e 1.")
    return score


def _threat(report):
    """Indicar se a execução contém alguma ameaça real, segundo ground_truth.events.

    Raises:
        ValueError: Se faltar ``ground_truth.events`` ou algum evento não tiver
            ``is_threat`` booleano.
    """
    truth = report.get("ground_truth")
    if not isinstance(truth, dict) or not isinstance(truth.get("events"), list):
        raise ValueError("A calibração exige ground_truth.events do avaliador.")
    events = truth["events"]
    if any(not isinstance(event, dict) or type(event.get("is_threat")) is not bool
           for event in events):
        raise ValueError("Cada evento de ground_truth exige is_threat booleano.")
    return any(event["is_threat"] for event in events)


def calibration_tables(records):
    """Devolver linhas dos quatro intervalos e linhas de cobertura por grupo.

    ``records`` contém os envelopes JSON ``{metrics, report}`` do coletor.
    ``metrics`` fornece scenario/variant e, opcionalmente, parametro/valor;
    estes dois últimos campos permitem separar experiências diferentes.
    A verdade vem exclusivamente de ground_truth, nunca de decisões ou scores.
    As fronteiras são [0,.25), [.25,.5), [.5,.75), [.75,1].

    Args:
        records (Iterable[dict[str, Any]]): Envelopes ``{metrics, report}`` do coletor.

    Returns:
        tuple[list[dict[str, Any]], list[dict[str, Any]]]: Linhas por intervalo (``n``,
            ameaças e frequência observada, ``None`` se vazio) e linhas de cobertura do
            score, ambas por grupo (cenário, variante, parâmetro, valor).

    Raises:
        ValueError: Se um envelope estiver malformado, faltar ``run_id``, o mesmo
            relatório aparecer duas vezes no grupo, ou o relatório for inválido.
    """
    groups = defaultdict(list)
    seen = set()
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("metrics"), dict):
            raise ValueError("Cada relatório exige o envelope {metrics, report} do coletor.")
        metadata, report = record["metrics"], record.get("report")
        if not isinstance(report, dict):
            raise ValueError("report deve ser um dicionário.")
        if any(not isinstance(metadata.get(name), str) or not metadata[name].strip()
               for name in ("scenario", "variant")):
            raise ValueError("metrics deve identificar scenario e variant.")
        run_id = report.get("run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("Cada relatório deve identificar run_id.")
        key = (metadata["scenario"], metadata["variant"],
               metadata.get("parametro", "reference"), str(metadata.get("valor", "current")))
        if not isinstance(key[2], str) or not key[2].strip():
            raise ValueError("parametro deve identificar o fator experimental.")
        identity = (*key, run_id)
        if identity in seen:
            raise ValueError(f"Relatório duplicado no mesmo grupo: {run_id}.")
        seen.add(identity)
        groups[key].append((initial_score(report), _threat(report)))

    bins, coverage = [], []
    for key, samples in sorted(groups.items()):
        metadata = dict(zip(("scenario", "variant", "parametro", "valor"), key))
        available = [(score, truth) for score, truth in samples if score is not None]
        for lower, upper in INTERVALS:
            values = [truth for score, truth in available
                      if lower <= score and (score < upper or upper == 1.0 and score == 1.0)]
            bins.append({
                **metadata, "interval_lower": lower, "interval_upper": upper,
                "interval": f"[{lower:.2f},{upper:.2f}{']' if upper == 1.0 else ')'}",
                "n": len(values), "threats": sum(values),
                "observed_threat_frequency": sum(values) / len(values) if values else None,
            })
        coverage.append({
            **metadata, "n_reports": len(samples), "n_with_score": len(available),
            "n_without_score": len(samples) - len(available),
            "threats_with_score": sum(truth for _, truth in available),
            "threats_without_score": sum(truth for score, truth in samples if score is None),
            "score_coverage": len(available) / len(samples),
        })
    return bins, coverage

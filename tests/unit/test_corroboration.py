import unittest

from isia.domain.models import Observation, Position
from isia.reasoning.corroboration import (
    aggregate_verification_responses,
    are_observations_compatible,
    classify_verification_response,
    decide_preliminary_verification,
    evaluate_preliminary_corroboration,
    select_eligible_sources,
)
from isia.simulation.scenario import Source
from isia.communication.messages import Message, MessageType, model_to_dict


def make_observation(event_id, position, observed_at, source_id=None):
    return Observation(
        event_id=event_id,
        source_id=source_id or f"sensor-{event_id}",
        event_type="possible_incident",
        position=Position(*position),
        observed_at=observed_at,
        confidence_score=0.8,
    )


def make_sources():
    return {
        "sensor-own": Source("acoustic", 10),
        "sensor-edge": Source("visual", 5),
        "sensor-near": Source("human", 3),
        "sensor-far": Source("acoustic", 2),
    }


def make_verification_response(
    observations,
    status="observations_available",
    message_id="response-001",
    conversation_id="conversation-001",
    request_message_id="request-001",
    response_source_id="sensor-02",
    hypothesis=None,
    absence=None,
    evidence_relation=None,
):
    payload = {
        "request_message_id": request_message_id,
        "observations": [model_to_dict(observation) for observation in observations],
        "status": status,
    }
    if hypothesis is not None:
        payload["hypothesis"] = hypothesis
    if absence is not None:
        payload["absence"] = absence
    if evidence_relation is not None:
        payload["evidence_relation"] = evidence_relation
    return Message(
        message_id,
        MessageType.VERIFY_RESPONSE,
        12.0,
        payload,
        incident_id="incident-001",
        source_id=response_source_id,
        conversation_id=conversation_id,
    )


def make_hypothesis(observation):
    return {
        "hypothesis_id": f"hypothesis-{observation.event_id}",
        "event_type": observation.event_type,
        "position": model_to_dict(observation.position),
        "valid_from": observation.observed_at,
        "valid_until": observation.observed_at,
    }


def make_informative_absence(initial, **overrides):
    hypothesis = make_hypothesis(initial)
    absence = {
        "hypothesis_id": hypothesis["hypothesis_id"],
        "declared_non_detection": True,
        "observed_from": initial.observed_at,
        "observed_until": initial.observed_at,
        "coverage": {
            "position": model_to_dict(initial.position),
            "radius": 2.0,
            "capability": "acoustic",
            "capability_validated": True,
            "opportunity_confirmed": True,
        },
    }
    absence.update(overrides)
    return make_verification_response(
        [],
        status="informative_absence",
        hypothesis=hypothesis,
        absence=absence,
    )


class TestObservationCompatibility(unittest.TestCase):

    def test_observacoes_proximas_e_no_mesmo_intervalo_sao_compativeis(self):
        first = make_observation("event-1", (0, 0), 10.0)
        second = make_observation("event-2", (3, 4), 12.0)

        self.assertTrue(are_observations_compatible(first, second, 5.0, 2.0))

    def test_observacoes_distantes_nao_sao_compativeis(self):
        first = make_observation("event-1", (0, 0), 10.0)
        second = make_observation("event-2", (6, 8), 10.0)

        self.assertFalse(are_observations_compatible(first, second, 5.0, 2.0))

    def test_observacoes_temporalmente_afastadas_nao_sao_compativeis(self):
        first = make_observation("event-1", (0, 0), 10.0)
        second = make_observation("event-2", (0, 0), 13.0)

        self.assertFalse(are_observations_compatible(first, second, 1.0, 2.0))

    def test_observacao_repetida_por_event_id_nao_e_contada_duas_vezes(self):
        first = make_observation("event-1", (0, 0), 10.0)
        repeated = make_observation("event-1", (0, 0), 10.0)

        self.assertFalse(
            are_observations_compatible(first, repeated, 1.0, 1.0)
        )

    def test_limites_invalidos_sao_rejeitados(self):
        first = make_observation("event-1", (0, 0), 10.0)
        second = make_observation("event-2", (0, 0), 10.0)

        with self.assertRaises(ValueError):
            are_observations_compatible(first, second, -1.0, 1.0)
        with self.assertRaises(ValueError):
            are_observations_compatible(first, second, 1.0, float("inf"))


class TestEligibleSources(unittest.TestCase):

    def setUp(self):
        self.observation = make_observation("event-1", (5, 0), 10.0, "sensor-own")
        self.positions = {
            "sensor-own": Position(0, 0),
            "sensor-edge": Position(0, 0),
            "sensor-near": Position(3, 0),
            "sensor-far": Position(0, 0),
        }
        self.sources = make_sources()

    def test_seleciona_sensores_dentro_e_no_limite_do_alcance(self):
        self.assertEqual(
            select_eligible_sources(self.observation, self.positions, self.sources),
            ("sensor-edge", "sensor-near"),
        )

    def test_exclui_a_fonte_original_e_considera_modalidades_diferentes(self):
        observation = make_observation("event-1", (0, 0), 10.0, "sensor-own")

        self.assertEqual(
            select_eligible_sources(observation, self.positions, self.sources),
            ("sensor-edge", "sensor-far", "sensor-near"),
        )

    def test_nao_seleciona_sensor_fora_do_alcance(self):
        observation = make_observation("event-1", (5, 0), 10.0, "sensor-own")

        self.assertNotIn(
            "sensor-far",
            select_eligible_sources(observation, self.positions, self.sources),
        )

    def test_sem_sensores_elegiveis_devolve_tuplo_vazio(self):
        observation = make_observation("event-1", (5, 5), 10.0, "sensor-own")

        self.assertEqual(
            select_eligible_sources(observation, self.positions, self.sources),
            (),
        )

    def test_resultado_e_deterministico_e_sem_duplicacoes(self):
        positions = {"sensor-z": Position(0, 0), "sensor-a": Position(0, 0)}
        sources = {"sensor-z": Source("visual", 10), "sensor-a": Source("human", 10)}
        observation = make_observation("event-1", (0, 0), 10.0)

        self.assertEqual(
            select_eligible_sources(observation, positions, sources),
            ("sensor-a", "sensor-z"),
        )


class TestVerificationResponseClassification(unittest.TestCase):

    def setUp(self):
        self.initial = make_observation("obs-001", (5, 5), 10.0, "sensor-01")
        self.absence_initial = Observation(
            "obs-001", "sensor-01", "gunshot_like_sound", Position(5, 5), 10.0, 0.8
        )

    def test_classifica_evidencia_compativel(self):
        response = make_verification_response(
            [make_observation("obs-002", (8, 5), 12.0, "sensor-02")]
        )

        result = classify_verification_response(self.initial, response, 3.0, 2.0)

        self.assertEqual(result, {
            "classification": "compatible",
            "observation_ids": ("obs-002",),
        })

    def test_tipos_diferentes_sem_regra_sao_inconclusivos(self):
        evidence = Observation(
            "obs-002", "sensor-02", "suspicious_movement",
            Position(8, 5), 12.0, 0.8
        )
        response = make_verification_response([evidence])

        result = classify_verification_response(self.initial, response, 3.0, 2.0)

        self.assertEqual(result["classification"], "inconclusive")
        self.assertEqual(result["observation_ids"], ("obs-002",))

    def test_tipos_diferentes_podem_ser_compatveis_com_regra_explicita(self):
        evidence = Observation(
            "obs-002", "sensor-02", "suspicious_movement",
            Position(8, 5), 12.0, 0.8
        )
        response = make_verification_response([evidence])

        result = classify_verification_response(
            self.initial,
            response,
            3.0,
            2.0,
            compatibility_rules={"possible_incident": {"suspicious_movement"}},
        )

        self.assertEqual(result["classification"], "compatible")
        self.assertEqual(result["observation_ids"], ("obs-002",))

    def test_observacoes_incompativeis_sao_inconclusivas(self):
        response = make_verification_response(
            [make_observation("obs-002", (20, 20), 12.0, "sensor-02")]
        )

        result = classify_verification_response(self.initial, response, 3.0, 2.0)

        self.assertEqual(result, {
            "classification": "inconclusive",
            "observation_ids": ("obs-002",),
        })

    def test_no_data_e_classificado_como_ausencia_de_dados(self):
        response = make_verification_response([], status="no_data")

        result = classify_verification_response(self.initial, response, 3.0, 2.0)

        self.assertEqual(result, {
            "classification": "no_data",
            "observation_ids": (),
        })

    def test_classifica_contradicao_apenas_com_regra_e_hipotese_correlacionada(self):
        contradictory = make_observation(
            "obs-contradictory", (5, 5), 10.0, "sensor-02"
        )
        contradictory = Observation(
            contradictory.event_id,
            contradictory.source_id,
            "contradictory_event",
            contradictory.position,
            contradictory.observed_at,
            contradictory.confidence_score,
        )
        response = make_verification_response(
            [contradictory],
            hypothesis=make_hypothesis(self.initial),
            evidence_relation="contradictory",
        )

        without_rule = classify_verification_response(
            self.initial, response, 1.0, 1.0
        )
        self.assertEqual(without_rule["classification"], "inconclusive")

        result = classify_verification_response(
            self.initial,
            response,
            1.0,
            1.0,
            incompatibility_rules={"possible_incident": {"contradictory_event"}},
        )
        self.assertEqual(result["classification"], "contradictory")
        self.assertEqual(result["observation_ids"], ("obs-contradictory",))

    def test_observacao_contraditoria_sem_hipotese_e_inconclusiva(self):
        contradictory = make_observation(
            "obs-contradictory", (5, 5), 10.0, "sensor-02"
        )
        response = make_verification_response([contradictory])
        response.payload["evidence_relation"] = "contradictory"

        result = classify_verification_response(
            self.initial,
            response,
            1.0,
            1.0,
            incompatibility_rules={"possible_incident": {"contradictory_event"}},
        )
        self.assertEqual(result["classification"], "inconclusive")

    def test_classifica_ausencia_informativa_com_cobertura_valida(self):
        response = make_informative_absence(self.absence_initial)

        result = classify_verification_response(self.absence_initial, response, 1.0, 1.0)

        self.assertEqual(result, {
            "classification": "informative_absence",
            "observation_ids": (),
        })

    def test_ausencia_sem_cobertura_valida_nao_e_informativa(self):
        cases = ("capability_validated", "opportunity_confirmed")
        for field in cases:
            with self.subTest(field=field):
                response = make_informative_absence(self.absence_initial)
                response.payload["absence"]["coverage"].pop(field)
                result = classify_verification_response(
                    self.absence_initial, response, 1.0, 1.0
                )
                self.assertEqual(result["classification"], "inconclusive")

    def test_ausencia_com_periodo_inadequado_nao_e_informativa(self):
        response = make_informative_absence(self.absence_initial)
        response.payload["absence"]["observed_from"] = 11.0

        result = classify_verification_response(self.absence_initial, response, 1.0, 1.0)

        self.assertEqual(result["classification"], "inconclusive")

    def test_repeticoes_nao_contam_como_evidencias_independentes(self):
        repeated = make_observation("obs-002", (5, 5), 10.0, "sensor-02")
        response = make_verification_response([repeated, repeated])

        result = classify_verification_response(self.initial, response, 0.0, 0.0)

        self.assertEqual(result["classification"], "compatible")
        self.assertEqual(result["observation_ids"], ("obs-002",))

    def test_rejeita_resposta_malformada(self):
        malformed = Message(
            "response-002",
            MessageType.VERIFY_RESPONSE,
            12.0,
            {"request_message_id": "request-001", "status": "no_data"},
            conversation_id="conversation-001",
        )

        with self.assertRaises(ValueError):
            classify_verification_response(self.initial, malformed, 3.0, 2.0)


class TestVerificationResponseAggregation(unittest.TestCase):

    def setUp(self):
        self.initial = make_observation("obs-001", (5, 5), 10.0, "sensor-01")
        self.absence_initial = Observation(
            "obs-001", "sensor-01", "gunshot_like_sound", Position(5, 5), 10.0, 0.8
        )

    def aggregate(self, responses, *, initial=None):
        return aggregate_verification_responses(
            self.initial if initial is None else initial,
            responses,
            "conversation-001",
            "request-001",
            3.0,
            2.0,
        )

    def test_mensagem_repetida_e_processada_apenas_uma_vez(self):
        evidence = make_observation("obs-002", (8, 5), 12.0, "sensor-02")
        response = make_verification_response([evidence])

        result = self.aggregate([response, response])

        self.assertEqual(result["classification"], "compatible")
        self.assertEqual(result["observation_ids"], ("obs-002",))
        self.assertEqual(result["compatible_source_count"], 1)

    def test_observacao_repetida_em_mensagens_diferentes_nao_duplica(self):
        evidence = make_observation("obs-002", (8, 5), 12.0, "sensor-02")
        responses = [
            make_verification_response([evidence], message_id="response-001"),
            make_verification_response([evidence], message_id="response-002"),
        ]

        result = self.aggregate(responses)

        self.assertEqual(result["observation_ids"], ("obs-002",))
        self.assertEqual(result["source_ids"], ("sensor-02",))

    def test_encaminhamento_nao_cria_uma_nova_fonte(self):
        evidence = make_observation("obs-002", (8, 5), 12.0, "sensor-02")
        forwarded = make_verification_response(
            [evidence],
            message_id="response-002",
            response_source_id="sensor-03",
        )

        result = self.aggregate([
            make_verification_response([evidence]),
            forwarded,
        ])

        self.assertEqual(result["source_ids"], ("sensor-02",))
        self.assertEqual(result["compatible_source_count"], 1)

    def test_varias_observacoes_da_mesma_fonte_contam_uma_fonte(self):
        responses = [
            make_verification_response([
                make_observation("obs-002", (8, 5), 12.0, "sensor-02"),
            ]),
            make_verification_response([
                make_observation("obs-003", (5, 8), 11.0, "sensor-02"),
            ], message_id="response-002"),
        ]

        result = self.aggregate(responses)

        self.assertEqual(result["observation_ids"], ("obs-002", "obs-003"))
        self.assertEqual(result["source_ids"], ("sensor-02",))
        self.assertEqual(result["compatible_source_count"], 1)

    def test_fontes_independentes_contam_separadamente(self):
        responses = [
            make_verification_response([
                make_observation("obs-002", (8, 5), 12.0, "sensor-02"),
            ]),
            make_verification_response([
                make_observation("obs-003", (5, 8), 11.0, "sensor-03"),
            ], message_id="response-002"),
        ]

        result = self.aggregate(responses)

        self.assertEqual(result["source_ids"], ("sensor-02", "sensor-03"))
        self.assertEqual(result["compatible_source_count"], 2)

    def test_respostas_sem_dados_mantem_ausencia_de_dados(self):
        result = self.aggregate([
            make_verification_response([], status="no_data"),
        ])

        self.assertEqual(result["classification"], "no_data")
        self.assertEqual(result["observation_ids"], ())
        self.assertEqual(result["compatible_source_count"], 0)

    def test_ausencia_informativa_contribui_para_cobertura_mas_nao_para_compatibilidade(self):
        result = self.aggregate(
            [make_informative_absence(self.absence_initial)],
            initial=self.absence_initial,
        )

        self.assertEqual(result["classification"], "informative_absence")
        self.assertEqual(result["informative_absence_source_ids"], ("sensor-02",))
        self.assertEqual(result["compatible_source_count"], 0)
        self.assertEqual(result["coverage_source_ids"], ("sensor-02",))

        evaluation = evaluate_preliminary_corroboration(
            result, ("sensor-02", "sensor-03")
        )
        self.assertEqual(evaluation["observed_source_ids"], ("sensor-02",))
        self.assertEqual(evaluation["compatible_source_count"], 0)
        self.assertEqual(evaluation["information_coverage"], 0.5)

    def test_conflito_entre_evidencias_fica_inconclusivo(self):
        compatible = make_observation("obs-compatible", (6, 5), 10.0, "sensor-02")
        contradictory = Observation(
            "obs-contradictory",
            "sensor-03",
            "contradictory_event",
            Position(5, 5),
            10.0,
            0.8,
        )
        hypothesis = make_hypothesis(self.initial)
        response_compatible = make_verification_response([compatible])
        response_contradictory = make_verification_response(
            [contradictory],
            message_id="response-002",
            response_source_id="sensor-03",
            hypothesis=hypothesis,
            evidence_relation="contradictory",
        )

        result = aggregate_verification_responses(
            self.initial,
            [response_compatible, response_contradictory],
            "conversation-001",
            "request-001",
            3.0,
            2.0,
            incompatibility_rules={"possible_incident": {"contradictory_event"}},
        )

        self.assertEqual(result["classification"], "inconclusive")
        self.assertEqual(result["compatible_observation_ids"], ("obs-compatible",))
        self.assertEqual(
            result["contradictory_observation_ids"], ("obs-contradictory",)
        )

    def test_resposta_de_outra_conversa_e_rejeitada(self):
        response = make_verification_response(
            [make_observation("obs-002", (8, 5), 12.0, "sensor-02")],
            conversation_id="other-conversation",
        )

        with self.assertRaises(ValueError):
            self.aggregate([response])

    def test_resposta_de_outro_pedido_e_rejeitada(self):
        response = make_verification_response(
            [make_observation("obs-002", (8, 5), 12.0, "sensor-02")],
            request_message_id="other-request",
        )

        with self.assertRaises(ValueError):
            self.aggregate([response])


class TestPreliminaryCorroboration(unittest.TestCase):

    def setUp(self):
        self.initial = make_observation("obs-001", (5, 5), 10.0, "sensor-01")

    def aggregate(self, responses):
        return aggregate_verification_responses(
            self.initial,
            responses,
            "conversation-001",
            "request-001",
            3.0,
            2.0,
        )

    def test_calcula_pontuacao_e_cobertura_com_fontes_compativeis(self):
        summary = self.aggregate([
            make_verification_response([
                make_observation("obs-002", (8, 5), 12.0, "sensor-02"),
            ]),
            make_verification_response([
                make_observation("obs-003", (20, 20), 12.0, "sensor-03"),
            ], message_id="response-002"),
        ])

        result = evaluate_preliminary_corroboration(
            summary, ("sensor-02", "sensor-03", "sensor-04")
        )

        self.assertEqual(result["compatible_source_ids"], ("sensor-02",))
        self.assertEqual(result["compatible_source_count"], 1)
        self.assertEqual(result["observed_source_count"], 2)
        self.assertEqual(result["preliminary_score"], 1 / 3)
        self.assertEqual(result["information_coverage"], 2 / 3)

    def test_duplicacoes_e_encaminhamento_nao_aumentam_indicadores(self):
        evidence = make_observation("obs-002", (8, 5), 12.0, "sensor-02")
        summary = self.aggregate([
            make_verification_response([evidence]),
            make_verification_response(
                [evidence], message_id="response-002", response_source_id="sensor-03"
            ),
        ])

        result = evaluate_preliminary_corroboration(summary, ("sensor-02", "sensor-03"))

        self.assertEqual(result["preliminary_score"], 1 / 2)
        self.assertEqual(result["information_coverage"], 1 / 2)
        self.assertEqual(result["observed_source_ids"], ("sensor-02",))

    def test_varias_observacoes_da_mesma_fonte_contam_uma_fonte(self):
        summary = self.aggregate([
            make_verification_response([
                make_observation("obs-002", (8, 5), 12.0, "sensor-02"),
                make_observation("obs-003", (5, 8), 11.0, "sensor-02"),
            ])
        ])

        result = evaluate_preliminary_corroboration(summary, ("sensor-02", "sensor-03"))

        self.assertEqual(result["compatible_source_count"], 1)
        self.assertEqual(result["observed_source_count"], 1)
        self.assertEqual(result["preliminary_score"], 1 / 2)
        self.assertEqual(result["information_coverage"], 1 / 2)

    def test_no_data_nao_evidencia_negativa(self):
        summary = self.aggregate([
            make_verification_response([], status="no_data"),
        ])

        result = evaluate_preliminary_corroboration(summary, ("sensor-02", "sensor-03"))

        self.assertEqual(result["classification"], "no_data")
        self.assertEqual(result["compatible_source_count"], 0)
        self.assertEqual(result["preliminary_score"], 0.0)
        self.assertEqual(result["information_coverage"], 0.0)

    def test_sem_fontes_elegiveis_indicadores_ficam_indisponiveis(self):
        summary = self.aggregate([
            make_verification_response([
                make_observation("obs-002", (8, 5), 12.0, "sensor-02"),
            ])
        ])

        result = evaluate_preliminary_corroboration(summary, ())

        self.assertIsNone(result["preliminary_score"])
        self.assertIsNone(result["information_coverage"])
        self.assertEqual(result["eligible_source_count"], 0)
        self.assertEqual(result["compatible_source_count"], 0)
        self.assertEqual(result["observed_source_count"], 0)

    def test_extremos_sem_observacoes_e_com_todas_as_fontes(self):
        summary = self.aggregate([
            make_verification_response([
                make_observation("obs-002", (8, 5), 12.0, "sensor-02"),
                make_observation("obs-003", (5, 8), 11.0, "sensor-03"),
            ])
        ])
        result = evaluate_preliminary_corroboration(summary, ("sensor-02", "sensor-03"))

        self.assertEqual(result["preliminary_score"], 1.0)
        self.assertEqual(result["information_coverage"], 1.0)

        no_data = self.aggregate([
            make_verification_response([], status="no_data"),
        ])
        result = evaluate_preliminary_corroboration(no_data, ("sensor-02", "sensor-03"))
        self.assertEqual(result["preliminary_score"], 0.0)
        self.assertEqual(result["information_coverage"], 0.0)


class TestPreliminaryVerificationDecision(unittest.TestCase):

    def evaluate(self, compatible_source_ids, observed_source_ids, eligible_count):
        compatible_source_ids = tuple(compatible_source_ids)
        observed_source_ids = tuple(observed_source_ids)
        return {
            "classification": "compatible" if compatible_source_ids else "inconclusive",
            "eligible_source_count": eligible_count,
            "compatible_source_ids": compatible_source_ids,
            "compatible_source_count": len(set(compatible_source_ids)),
            "observed_source_ids": observed_source_ids,
            "observed_source_count": len(set(observed_source_ids)),
            "preliminary_score": (
                len(set(compatible_source_ids)) / eligible_count
                if eligible_count else None
            ),
            "information_coverage": (
                len(set(observed_source_ids)) / eligible_count
                if eligible_count else None
            ),
        }

    def test_pede_verificacao_movel_quando_atinge_o_minimo(self):
        summary = self.evaluate(("sensor-02", "sensor-03"), ("sensor-02", "sensor-03"), 3)

        result = decide_preliminary_verification(summary, 2)

        self.assertEqual(result["decision"], "request_mobile_verification")
        self.assertEqual(result["reason"], "compatible_source_threshold_reached")
        self.assertEqual(result["compatible_source_ids"], ("sensor-02", "sensor-03"))

    def test_continua_a_observar_com_evidencia_insuficiente(self):
        summary = self.evaluate(("sensor-02",), ("sensor-02",), 2)

        result = decide_preliminary_verification(summary, 2)

        self.assertEqual(result["decision"], "observe")
        self.assertEqual(result["reason"], "insufficient_compatible_evidence")

    def test_no_data_nao_produz_decisao_de_confirmacao(self):
        summary = self.evaluate((), (), 2)
        summary["classification"] = "no_data"
        summary["preliminary_score"] = 0.0
        summary["information_coverage"] = 0.0

        result = decide_preliminary_verification(summary, 1)

        self.assertEqual(result["decision"], "observe")
        self.assertEqual(result["reason"], "no_information")
        self.assertEqual(result["compatible_source_count"], 0)

    def test_fontes_duplicadas_nao_atingem_o_minimo_independentemente(self):
        summary = self.evaluate(
            ("sensor-02", "sensor-02"),
            ("sensor-02", "sensor-02"),
            2,
        )

        result = decide_preliminary_verification(summary, 2)

        self.assertEqual(result["decision"], "observe")
        self.assertEqual(result["compatible_source_count"], 1)

    def test_sem_fontes_elegiveis_devolve_observe_e_indicadores_indisponiveis(self):
        summary = self.evaluate((), (), 0)

        result = decide_preliminary_verification(summary, 1)

        self.assertEqual(result["decision"], "observe")
        self.assertEqual(result["reason"], "no_eligible_sources")
        self.assertIsNone(result["preliminary_score"])
        self.assertIsNone(result["information_coverage"])

    def test_rejeita_limiar_invalido(self):
        summary = self.evaluate(("sensor-02",), ("sensor-02",), 1)

        with self.assertRaises(ValueError):
            decide_preliminary_verification(summary, 0)
        with self.assertRaises(TypeError):
            decide_preliminary_verification(summary, True)

    def test_limite_exato_e_valor_extremo(self):
        summary = self.evaluate(("sensor-02",), ("sensor-02",), 1)

        result = decide_preliminary_verification(summary, 1)

        self.assertEqual(result["decision"], "request_mobile_verification")
        self.assertEqual(result["preliminary_score"], 1.0)
        self.assertEqual(result["information_coverage"], 1.0)

if __name__ == "__main__":
    unittest.main()

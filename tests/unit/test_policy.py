"""Scores explicáveis, correlação, extremos e sensibilidade da mobilização."""

import json
import unittest
from dataclasses import replace
from pathlib import Path

from isia.communication.messages import Message, MessageType, model_to_dict
from isia.domain.models import Incident, Observation, Position
from isia.reasoning.allocation import MissionRegistry
from isia.reasoning.corroboration import (
    aggregate_verification_responses, build_observation_hypothesis, evaluate_reputation_corroboration,
)
from isia.reasoning.policy import ResponsePolicy, decide_response
from isia.reasoning.reputation import EvaluationResult, ReputationBook


def obs(identifier="initial", source="s1", *, at=10, position=Position(5, 5), confidence=1):
    return Observation(identifier, source, "gunshot_like_sound", position, at, confidence)


class TestResponsePolicy(unittest.TestCase):
    def setUp(self):
        self.initial = obs()
        self.profiles = {
            "s1": {"modality": "acoustic", "correlation_group": "g1"},
            "s2": {"modality": "visual", "correlation_group": "g2"},
        }
        self.policy = ResponsePolicy()

    def evaluate(self, observations=(), *, reputations=None, profiles=None, initial=None, responses=None):
        initial = initial or self.initial
        if responses is None:
            responses = [Message(
                "reply", MessageType.VERIFY_RESPONSE, 20,
                {"request_message_id": "request", "status": "observations_available" if observations else "no_data",
                 "observations": [model_to_dict(item) for item in observations]},
                conversation_id="conversation", incident_id="incident", source_id="s2",
            )]
        aggregate = aggregate_verification_responses(
            initial, responses, "conversation", "request", 2, 2, expected_incident_id="incident",
            incompatibility_rules={"gunshot_like_sound": {"benign_explanation"}},
        )
        return evaluate_reputation_corroboration(
            initial, aggregate, tuple(item.source_id for item in observations),
            reputations if reputations is not None else {},
            profiles if profiles is not None else self.profiles, 2, 2,
        )

    def decide(self, evaluation, *, severity=0.5, policy=None, mission=None):
        return decide_response(evaluation, policy or self.policy, severity=severity,
                               initial_observation=self.initial, incident_id="incident", mission_result=mission)

    def mission(self, **changes):
        values = dict(result_id="mission-result", incident_id="incident", observation_ids=("initial",),
                      outcome="confirmed", basis="independent_mission", evaluated_at=12,
                      evidence_ids=("independent-patrol-report",), evidence_source_ids=("patrol",),
                      final=True, sufficient_coverage=True)
        return EvaluationResult(**(values | changes))

    def test_new_sources_have_reproducible_explainable_score(self):
        evaluation = self.evaluate([obs("other", "s2")])
        self.assertEqual(evaluation["suspicion_score"], 0.5)
        self.assertEqual(evaluation["supporting_group_count"], 2)
        self.assertEqual(evaluation["modalities"], ("acoustic", "visual"))
        self.assertEqual(evaluation["score_kind"], "heuristic_not_probability")
        decision = self.decide(evaluation)
        self.assertEqual(decision["decision"], "request_mobile_verification")
        self.assertEqual(decision["policy"]["patrol_threshold"], 0.25)
        self.assertEqual(len(decision["factors"]), 2)
        json.dumps(decision, allow_nan=False)

    def test_incorrect_history_reduces_score_and_changes_decision(self):
        observations = [obs("other", "s2")]
        reliable = self.evaluate(observations, reputations={"s1": 0.9, "s2": 0.9})
        unreliable = self.evaluate(observations, reputations={"s1": 0.1, "s2": 0.1})
        self.assertEqual(self.decide(reliable)["decision"], "request_rangers")
        self.assertEqual(self.decide(unreliable)["decision"], "observe")
        self.assertLess(unreliable["suspicion_score"], reliable["suspicion_score"])

    def test_same_modality_limits_mobilization(self):
        profiles = {key: value | {"modality": "acoustic"} for key, value in self.profiles.items()}
        evaluation = self.evaluate([obs("other", "s2")], reputations={"s1": 1, "s2": 1}, profiles=profiles)
        self.assertEqual(evaluation["suspicion_score"], 0.75)
        self.assertEqual(self.decide(evaluation)["decision"], "request_mobile_verification")

    def test_correlated_false_reports_cannot_multiply_support(self):
        profiles = {f"s{i}": {"modality": "acoustic", "correlation_group": "shared_noise"} for i in range(1, 30)}
        one = self.evaluate([obs("o2", "s2")], profiles=profiles)
        many = self.evaluate([obs(f"o{i}", f"s{i}") for i in range(2, 30)], profiles=profiles)
        self.assertEqual(one["suspicion_score"], many["suspicion_score"])
        self.assertEqual(many["supporting_group_count"], 1)
        self.assertEqual(self.decide(many)["decision"], "observe")
        unknown = self.evaluate([obs(f"o{i}", f"s{i}") for i in range(2, 30)], profiles={})
        self.assertEqual(unknown["supporting_group_count"], 1)
        self.assertEqual(unknown["modalities"], ())

    def test_duplicate_forwarded_and_reordered_observations_do_not_change_score(self):
        evidence = obs("other", "s2")
        plain = self.evaluate([evidence])
        repeated = self.evaluate([evidence, evidence, evidence])
        self.assertEqual(plain, repeated)
        observations = [evidence, obs("third", "s2", at=11)]
        self.assertEqual(self.evaluate(observations), self.evaluate(list(reversed(observations))))

    def test_time_space_and_confidence_attenuate_weights(self):
        baseline = self.evaluate([obs("other", "s2")])
        for evidence in (obs("other", "s2", at=12), obs("other", "s2", position=Position(7, 5)),
                         obs("other", "s2", confidence=0.1), obs("other", "s2", at=13)):
            with self.subTest(evidence=evidence):
                self.assertLess(self.evaluate([evidence])["suspicion_score"], baseline["suspicion_score"])

    def test_no_confirmation_never_closes_and_severity_requests_verification(self):
        evaluation = self.evaluate()
        self.assertEqual(evaluation["suspicion_score"], 0.1875)
        self.assertEqual(self.decide(evaluation)["decision"], "observe")
        self.assertEqual(self.decide(evaluation, severity=1)["decision"], "request_mobile_verification")
        zero = self.evaluate(initial=obs(confidence=0))
        self.assertEqual(self.decide(zero, severity=1)["decision"], "observe")
        self.assertEqual(evaluation, self.evaluate(responses=[]))

    def test_policy_threshold_and_severity_sensitivity(self):
        evaluation = self.evaluate([obs("other", "s2")])
        actions = [self.decide(evaluation, policy=replace(self.policy, patrol_threshold=value))["decision"]
                   for value in (0.49, 0.5, 0.51)]
        self.assertEqual(actions, ["request_mobile_verification", "request_mobile_verification", "observe"])
        evaluation = self.evaluate()
        actions = [self.decide(evaluation, severity=value)["decision"] for value in (0.79, 0.8, 0.81)]
        self.assertEqual(actions, ["observe", "request_mobile_verification", "request_mobile_verification"])
        strong = self.evaluate([obs("other", "s2")], reputations={"s1": 0.7, "s2": 0.7})
        actions = [self.decide(strong, policy=replace(self.policy, ranger_threshold=value))["decision"]
                   for value in (0.69, 0.7, 0.71)]
        self.assertEqual(actions, ["request_rangers", "request_rangers", "request_mobile_verification"])

    def test_extremes_and_conflict(self):
        for value in (0, 1):
            evaluation = self.evaluate([obs("other", "s2")], reputations={"s1": value, "s2": value})
            self.assertEqual(evaluation["suspicion_score"], value)
        evaluation["conflicting_evidence"] = True
        self.assertEqual(self.decide(evaluation)["decision"], "request_mobile_verification")

    def test_zero_weight_extra_source_does_not_dilute_existing_evidence(self):
        evidence = [obs("other", "s2")]
        baseline = self.evaluate(evidence)
        profiles = self.profiles | {"s3": {"modality": "human", "correlation_group": "g3"}}
        extended = self.evaluate(evidence + [obs("zero", "s3", confidence=0)], profiles=profiles)
        self.assertEqual(baseline["suspicion_score"], extended["suspicion_score"])

    def test_contradiction_and_informative_absence_reduce_support_without_learning(self):
        hypothesis = build_observation_hypothesis(self.initial)
        contrary = replace(obs("contrary", "s2"), event_type="benign_explanation")
        negative = Message(
            "reply", MessageType.VERIFY_RESPONSE, 12,
            {"request_message_id": "request", "status": "observations_available",
             "observations": [model_to_dict(contrary)], "hypothesis": hypothesis,
             "evidence_relation": "contradictory"},
            conversation_id="conversation", incident_id="incident", source_id="s2",
        )
        absence = Message(
            "absence", MessageType.VERIFY_RESPONSE, 12,
            {"request_message_id": "request", "status": "informative_absence", "observations": [],
             "hypothesis": hypothesis, "absence": {
                 "hypothesis_id": hypothesis["hypothesis_id"], "declared_non_detection": True,
                 "observed_from": 10, "observed_until": 10,
                 "coverage": {"position": model_to_dict(self.initial.position), "radius": 2,
                              "capability": "acoustic", "capability_validated": True,
                              "opportunity_confirmed": True}}},
            conversation_id="conversation", incident_id="incident", source_id="s2",
        )
        book = ReputationBook()
        for response in (negative, absence):
            with self.subTest(response=response.message_id):
                evaluation = self.evaluate([contrary], responses=[response], reputations=book.snapshot(("s1", "s2")))
                self.assertEqual(evaluation["suspicion_score"], 0)
                self.assertGreater(evaluation["opposition"], 0)
                self.assertEqual(self.decide(evaluation)["decision"], "observe")
        self.assertEqual(book.history, [])
        self.assertEqual(book.score("s1"), 0.5)

    def test_conflicting_observation_variants_are_excluded(self):
        evaluation = self.evaluate([obs("other", "s2"), obs("other", "s2", confidence=0.2)])
        self.assertEqual(evaluation["suspicion_score"], self.evaluate()["suspicion_score"])
        self.assertTrue(evaluation["conflicting_evidence"])

    def test_mission_results_need_independent_conclusive_reference(self):
        evaluation = self.evaluate()
        self.assertEqual(self.decide(evaluation, mission=self.mission())["decision"], "request_rangers")
        self.assertEqual(self.decide(evaluation, mission=self.mission(outcome="refuted"))["decision"], "close")
        for changes in ({"outcome": "inconclusive"}, {"outcome": "failed"}, {"final": False},
                        {"sufficient_coverage": False}, {"incident_id": "other"}, {"evaluated_at": 9},
                        {"evidence_source_ids": ("s1",)}, {"observation_ids": ("other",)}):
            with self.subTest(changes=changes):
                decision = self.decide(evaluation, mission=self.mission(**changes))
                self.assertEqual(decision["decision"], "observe")
                self.assertIsNotNone(decision["mission_rejection"])
        with self.assertRaises(ValueError):
            self.decide(evaluation, mission=self.mission(basis="ground_truth"))

    def test_config_and_bridge_to_existing_mission_registry(self):
        root = Path(__file__).resolve().parents[2]
        settings = json.loads((root / "config/agents.json").read_text())
        policy = ResponsePolicy(**settings["policy"])
        book = ReputationBook(**settings["reputation"])
        self.assertEqual(book.score("new"), 0.5)
        evaluation = self.evaluate([obs("other", "s2")])
        decision = self.decide(evaluation, policy=policy)
        registry = MissionRegistry()
        incident = Incident("incident", (self.initial,))
        mission = registry.create_from_decision(incident, decision)
        self.assertIsNotNone(mission)
        self.assertIs(mission, registry.create_from_decision(incident, decision))

    def test_invalid_configuration_is_rejected(self):
        for changes in ({"patrol_threshold": True}, {"ranger_threshold": float("nan")},
                        {"patrol_threshold": 0.9}, {"severe_patrol_threshold": 0},
                        {"ranger_min_groups": 1}, {"ranger_min_modalities": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                ResponsePolicy(**changes)
        with self.assertRaises(ValueError):
            self.evaluate(reputations={"s1": float("inf")})
        with self.assertRaises(ValueError):
            self.decide(self.evaluate(), severity=True)


if __name__ == "__main__":
    unittest.main()

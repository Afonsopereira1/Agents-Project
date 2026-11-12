"""Execuções identificadas não colidem; reprocessar uma amostra não a duplica."""

from dataclasses import replace
import unittest

from isia.domain.models import Observation, Position
from isia.reasoning.reputation import EvaluationResult, ReputationBook


class TestReputationRunScope(unittest.TestCase):
    def setUp(self):
        self.observation = Observation("obs-1", "sensor", "gunshot_like_sound", Position(1, 1), 0, 0.8)
        self.result = EvaluationResult(
            "evaluation", "incident", ("obs-1",), "confirmed", "independent_mission", 1,
            evidence_ids=("inspection",), evidence_source_ids=("patrol",),
            final=True, sufficient_coverage=True,
        )

    def test_identified_runs_can_evaluate_their_own_observations(self):
        book = ReputationBook()
        for run_id in ("run-a", "run-b"):
            update = book.update(self.observation, "incident", self.result, run_id=run_id)
            self.assertTrue(update["updated"])
            self.assertEqual(update["run_id"], run_id)
        self.assertEqual(book.score("sensor"), 4 / 6)
        self.assertEqual(book.history[-1]["counts"], (2, 0))

    def test_same_run_deduplicates_result_replays_and_source_incident(self):
        book = ReputationBook()
        book.update(self.observation, "incident", self.result, run_id="run-a")
        second = replace(self.observation, event_id="obs-2")
        candidates = (
            (self.observation, self.result),
            (self.observation, replace(self.result, result_id="new-result-id")),
            (second, replace(self.result, observation_ids=("obs-2",))),
        )
        for observation, result in candidates:
            with self.subTest(observation=observation.event_id, result=result.result_id):
                record = book.update(observation, "incident", result, run_id="run-a")
                self.assertEqual((record["updated"], record["reason"]), (False, "already_evaluated"))
        self.assertEqual(book.score("sensor"), 0.6)

    def test_calls_without_scope_keep_existing_idempotence(self):
        book = ReputationBook()
        first = book.update(self.observation, "incident", self.result)
        second = book.update(self.observation, "incident", self.result)
        self.assertTrue(first["updated"])
        self.assertIsNone(first["run_id"])
        self.assertEqual(second["reason"], "already_evaluated")
        self.assertEqual(book.score("sensor"), 0.6)

    def test_invalid_run_ids_do_not_change_history(self):
        book = ReputationBook()
        for run_id in ("", " ", True, 1, []):
            with self.subTest(run_id=run_id), self.assertRaises(ValueError):
                book.update(self.observation, "incident", self.result, run_id=run_id)
        self.assertEqual(book.history, [])
        self.assertEqual(book.score("sensor"), 0.5)

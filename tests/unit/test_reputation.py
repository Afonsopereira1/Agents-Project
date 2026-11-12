"""Aprendizagem só com referência externa suficiente e sem contagens repetidas."""

import json
import unittest
from dataclasses import replace

from isia.domain.models import Observation, Position
from isia.communication.messages import Message, MessageType
from isia.reasoning.reputation import (
    EvaluationResult, ReputationBook, result_from_ground_truth, result_from_mission,
)
from isia.simulation.scenario import Event, Scenario, Source
from isia.simulation.world import World


def observation(event_id="obs-1", source_id="sensor-1"):
    return Observation(event_id, source_id, "gunshot_like_sound", Position(5, 5), 10.0, 0.8)


def result(**changes):
    values = dict(
        result_id="result-1", incident_id="incident-1", observation_ids=("obs-1",),
        outcome="confirmed", basis="independent_mission", evaluated_at=12.0,
        evidence_ids=("patrol-report-1",), evidence_source_ids=("patrol-1",),
        final=True, sufficient_coverage=True,
    )
    return EvaluationResult(**(values | changes))


class TestReputation(unittest.TestCase):
    def test_new_source_and_small_sample_are_smoothed(self):
        book = ReputationBook()
        self.assertEqual(book.score("sensor-1"), 0.5)
        update = book.update(observation(), "incident-1", result())
        self.assertTrue(update["updated"])
        self.assertEqual(update["after"], 3 / 5)
        self.assertEqual(update["counts"], (1, 0))
        self.assertEqual(book.score("new-source"), 0.5)
        json.dumps(book.history, allow_nan=False)

    def test_historically_incorrect_source_and_recovery(self):
        book = ReputationBook()
        for index in range(20):
            obs = observation(f"obs-{index}")
            verdict = result(incident_id=f"incident-{index}", observation_ids=(obs.event_id,), outcome="refuted")
            book.update(obs, verdict.incident_id, verdict)
        self.assertEqual(book.score("sensor-1"), 2 / 24)
        obs = observation("recovery")
        verdict = result(incident_id="recovery", observation_ids=(obs.event_id,))
        book.update(obs, "recovery", verdict)
        self.assertEqual(book.score("sensor-1"), 3 / 25)

    def test_unjustified_results_never_change_counts(self):
        variants = (
            {"basis": "consensus"}, {"outcome": "inconclusive"}, {"outcome": "failed"},
            {"final": False}, {"sufficient_coverage": False}, {"evidence_ids": ()},
            {"evidence_source_ids": ()}, {"evidence_source_ids": ("sensor-1",)},
            {"evidence_ids": ("obs-1",)}, {"evaluated_at": 9.0},
            {"incident_id": "unrelated"}, {"observation_ids": ("unrelated",)},
        )
        book = ReputationBook()
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertFalse(book.update(observation(), "incident-1", result(**variant))["updated"])
                self.assertEqual(book.score("sensor-1"), 0.5)
        self.assertTrue(book.update(observation(), "incident-1", result())["updated"])

    def test_replays_other_result_ids_and_same_incident_samples_count_once(self):
        book = ReputationBook()
        verdict = result(observation_ids=("obs-1", "obs-2"))
        book.update(observation(), "incident-1", verdict)
        for obs, candidate in (
            (observation(), verdict),
            (observation(), replace(verdict, result_id="replay", outcome="refuted")),
            (observation("obs-2"), verdict),
            (observation(), replace(verdict, incident_id="renamed")),
        ):
            self.assertFalse(book.update(obs, candidate.incident_id, candidate)["updated"])
        self.assertEqual(book.score("sensor-1"), 0.6)
        self.assertTrue(book.update(observation("obs-2", "sensor-2"), "incident-1", verdict)["updated"])

    def test_invalid_parameters_and_reference_fields(self):
        for value in (0, -1, True, float("nan"), float("inf"), "2"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ReputationBook(alpha=value)
        with self.assertRaises(ValueError):
            ReputationBook(1e308, 1e308)
        for changes in ({"final": 1}, {"evaluated_at": float("nan")},
                        {"observation_ids": ()}, {"observation_ids": ("a", "a")},
                        {"basis": "vote"}, {"outcome": "not_confirmed"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                result(**changes)

    def test_configured_prior_is_used(self):
        book = ReputationBook(alpha=3, beta=1)
        self.assertEqual(book.score("new"), 0.75)
        book.update(observation(), "incident-1", result(outcome="refuted"))
        self.assertEqual(book.score("sensor-1"), 3 / 5)

    def test_simulator_reference_is_evaluator_only_and_requires_finished_event(self):
        scenario = Scenario(
            World(10, 10, {"s": Position(5, 5)}),
            {"s": Source("acoustic", 2, false_positive_rate=1)},
            (Event("thunder", "thunder", Position(5, 5), 0, 2),), 1, 5,
        )
        obs = scenario.source("s").recent()[0]
        book = ReputationBook()
        active = result_from_ground_truth(obs, "i", scenario.ground_truth, evaluated_at=0, run_id="run-1")
        self.assertFalse(book.update(obs, "i", active)["updated"])
        scenario.advance(3)
        final = result_from_ground_truth(obs, "i", scenario.ground_truth, evaluated_at=3, run_id="run-1")
        self.assertEqual(final.outcome, "refuted")
        self.assertTrue(book.update(obs, "i", final)["updated"])
        self.assertEqual(book.score("s"), 0.4)
        missing = result_from_ground_truth(observation("missing"), "i", scenario.ground_truth,
                                          evaluated_at=12, run_id="run-1")
        self.assertEqual(missing.outcome, "inconclusive")
        self.assertFalse(hasattr(scenario.source("s"), "ground_truth"))



def mission_result(**payload):
    values = {"outcome": "confirmed", "reason": "local_inspection", "completed_at": 14.0,
              "position": {"x": 5, "y": 6}, "task": "verify_incident", "resource_id": "drone",
              "accept_message_id": "accept-1"}
    values |= payload
    return Message("result-1", MessageType.MISSION_RESULT, max(15.0, values["completed_at"]), values,
                   incident_id="incident-1", mission_id="mission-1", source_id="drone",
                   conversation_id="conversation-1")


class TestMissionAdjudication(unittest.TestCase):
    limits = {"max_distance": 1, "max_delay_seconds": 30.0}

    def update(self, message, book=None):
        book = book or ReputationBook()
        return book.update(observation(), "incident-1",
                           result_from_mission(message, observation(), "incident-1", **self.limits))

    def test_covered_confirmation_updates_once(self):
        book = ReputationBook()
        self.assertEqual(self.update(mission_result(), book)["reason"], "grounded_result")
        self.assertEqual(book.score("sensor-1"), 0.6)
        self.assertEqual(self.update(mission_result(), book)["reason"], "already_evaluated")

    def test_non_detection_ranger_and_missing_coverage_do_not_learn(self):
        for payload, reason in (
            ({"outcome": "not_confirmed"}, "unresolved_result"),
            ({"outcome": "failed"}, "unresolved_result"),
            ({"task": "respond_incident"}, "unresolved_result"),
            ({"position": {"x": 9, "y": 9}}, "insufficient_reference"),
            ({"completed_at": 100.0}, "insufficient_reference"),
            ({"completed_at": 5.0}, "insufficient_reference"),
            ({"position": None}, "insufficient_reference"),
        ):
            with self.subTest(payload=payload):
                record = self.update(mission_result(**payload))
                self.assertEqual((record["updated"], record["reason"]), (False, reason))

    def test_patrol_cannot_validate_itself(self):
        own = Observation("obs-1", "drone", "gunshot_like_sound", Position(5, 5), 10.0, 0.8)
        evaluation = result_from_mission(mission_result(), own, "incident-1", **self.limits)
        self.assertEqual(evaluation.rejection_reason(own, "incident-1"), "non_independent_reference")

    def test_invalid_limits_are_rejected(self):
        with self.assertRaises(ValueError):
            result_from_mission(mission_result(), observation(), "incident-1",
                                max_distance=-1, max_delay_seconds=1)


if __name__ == "__main__":
    unittest.main()

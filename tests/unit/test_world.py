import json
import random
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from isia.communication.messages import model_to_dict
from isia.domain.models import Incident, Position
from isia.simulation.movement import position_at
from isia.simulation.scenario import Event, Scenario, Source
from isia.simulation.world import World


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/environment.json"


class TestWorldObservations(unittest.TestCase):
    def scenario(self, source=None, event=None, seed=42, window=2):
        return Scenario(World(10, 10, {"s1": Position(0, 0)}),
                        {"s1": source or Source("acoustic", 5)},
                        (event or Event("real-secret", "threat", Position(3, 4), 0, 10),),
                        seed, window)

    def test_minimal_scenario_has_two_nearby_sources_and_unique_observations(self):
        scenario = Scenario.from_config(CONFIG)
        self.assertEqual(scenario.ground_truth["events"][0]["state"], "pending")
        self.assertTrue(all(not scenario.source(key).recent() for key in scenario.world.sensors))
        scenario.advance(1)
        observations = tuple(obs for key in scenario.world.sensors
                             for obs in scenario.source(key).recent())
        self.assertEqual(len(observations), 2)
        self.assertEqual({obs.source_id for obs in observations}, {"sensor_01", "sensor_02"})
        self.assertEqual(len(Incident("incident-1", observations).observations), 2)
        for key in scenario.world.sensors:
            self.assertTrue(all(obs.source_id == key for obs in scenario.source(key).recent()))

    def test_range_inclusive_and_no_observation_outside_range(self):
        self.assertEqual(len(self.scenario().source("s1").recent()), 1)  # distance 5
        scenario = self.scenario(Source("acoustic", 4.999))
        self.assertEqual(scenario.source("s1").recent(), ())
        scenario = self.scenario(Source("acoustic", 0),
                                 Event("e", "threat", Position(0, 0), 0, 1))
        self.assertEqual(len(scenario.source("s1").recent()), 1)

    def test_detection_and_false_negative_extremes(self):
        for sensitivity, false_negative, expected in ((1, 0, 1), (0, 0, 0), (1, 1, 0)):
            with self.subTest(sensitivity=sensitivity, false_negative=false_negative):
                scenario = self.scenario(Source("acoustic", 5, sensitivity=sensitivity,
                                                false_negative_rate=false_negative))
                self.assertEqual(len(scenario.source("s1").recent()), expected)

    def test_benign_events_and_heterogeneous_capabilities(self):
        for kind, channels in (("thunder", {"acoustic"}), ("tourist", {"visual", "human"})):
            for channel in ("acoustic", "visual", "human"):
                for rate in (0, 1):
                    with self.subTest(kind=kind, channel=channel, rate=rate):
                        scenario = self.scenario(
                            Source(channel, 5, false_positive_rate=rate),
                            Event("benign-secret", kind, Position(3, 4), 0, 1))
                        observations = scenario.source("s1").recent()
                        self.assertEqual(len(observations), int(channel in channels and rate == 1))
                        self.assertFalse(scenario.ground_truth["events"][0]["is_threat"])
                        if observations:
                            self.assertNotIn(kind, json.dumps(model_to_dict(observations[0])))
        scenario = Scenario(World(1, 1, {"s1": Position(0, 0)}),
                            {"s1": Source("human", 0, false_positive_rate=1)}, (), 42)
        self.assertEqual(scenario.source("s1").recent(), ())

    def test_agent_feed_does_not_expose_truth_or_other_sources(self):
        scenario = self.scenario()
        feed = scenario.source("s1")
        self.assertFalse(hasattr(feed, "ground_truth"))
        self.assertFalse(hasattr(feed, "world"))
        self.assertFalse(hasattr(feed, "_events"))
        observation = feed.recent()[0]
        self.assertEqual(set(model_to_dict(observation)), {
            "event_id", "source_id", "event_type", "position", "observed_at",
            "confidence_score", "intensity_score"})
        self.assertNotIn("real-secret", json.dumps(model_to_dict(observation)))
        self.assertEqual(scenario.ground_truth["observations"][observation.event_id], "real-secret")
        snapshot = scenario.ground_truth
        snapshot["events"][0]["position"]["x"] = 99
        snapshot["observations"].clear()
        self.assertEqual(scenario.ground_truth["events"][0]["position"], {"x": 3, "y": 4})
        self.assertTrue(scenario.ground_truth["observations"])
        with self.assertRaises(KeyError):
            scenario.source("unknown")

    def test_event_boundaries_and_corroboration_window(self):
        scenario = self.scenario(event=Event("e", "threat", Position(3, 4), 1, 1))
        feed = scenario.source("s1")
        self.assertEqual(feed.recent(), ())
        scenario.advance(1)
        original = feed.recent()
        self.assertEqual(original[0].observed_at, 1)
        self.assertEqual(feed.recent(), original)  # a consulta não volta a sortear
        scenario.advance(1)  # fim exclusivo, sem nova leitura
        self.assertEqual(feed.recent(), original)
        self.assertEqual(scenario.ground_truth["events"][0]["state"], "ended")
        scenario.advance(1)  # início da janela inclusivo
        self.assertEqual(feed.recent(), original)
        scenario.advance(0.01)
        self.assertEqual(feed.recent(), ())
        self.assertEqual(original[0].observed_at, 1)

    def test_sampling_does_not_invent_events_between_steps(self):
        scenario = self.scenario(event=Event("e", "threat", Position(0, 0), 1, 1))
        scenario.advance(3)
        self.assertEqual(scenario.source("s1").recent(), ())
        self.assertEqual(scenario.ground_truth["events"][0]["state"], "ended")

    def test_movement_fractional_steps_and_range_follow_the_same_clock(self):
        event = Event("moving", "threat", Position(0, 0), 1, 10, Position(4, 2), 2)
        scenario = self.scenario(Source("acoustic", 1), event)
        for seconds, position in ((1, Position(0, 0)), (0.25, Position(0, 0)),
                                  (0.25, Position(1, 0)), (0.5, Position(2, 0)),
                                  (2, Position(4, 2))):
            scenario.advance(seconds)
            self.assertEqual(scenario.ground_truth["events"][0]["position"], model_to_dict(position))
        self.assertEqual(len(scenario.ground_truth["observations"]), 3)
        self.assertEqual(event.position_at(100), Position(4, 2))
        self.assertEqual(position_at(Position(4, 2), Position(0, 0), 2, 2.5), Position(0, 1))
        self.assertEqual(position_at(Position(0, 0), Position(4, 2), 0, 100), Position(0, 0))
        self.assertEqual(position_at(Position(0, 0), Position(4, 2), 1e308, 1e308), Position(4, 2))

    def test_position_noise_stays_inside_map_and_is_not_always_exact(self):
        scenario = self.scenario(Source("acoustic", 5, position_error=2),
                                 Event("e", "threat", Position(0, 0), 0, 50))
        for _ in range(30):
            scenario.advance()
        observations = scenario.source("s1").recent()
        self.assertTrue(any(obs.position != Position(0, 0) for obs in observations))
        for obs in observations:
            self.assertTrue(scenario.world.contains(obs.position))
            self.assertLessEqual(obs.position.x, 2)
            self.assertLessEqual(obs.position.y, 2)

    def test_seed_replay_query_order_and_global_random_are_independent(self):
        first = Scenario.from_config(CONFIG)
        second = Scenario.from_config(CONFIG)
        global_state = random.getstate()
        for _ in range(8):
            for key in reversed(tuple(first.world.sensors)):
                first.source(key).recent()
                first.source(key).recent()
            first.advance(0.5)
            second.advance(0.5)
            self.assertEqual(first.ground_truth, second.ground_truth)
            for key in first.world.sensors:
                self.assertEqual(first.source(key).recent(), second.source(key).recent())
        self.assertEqual(random.getstate(), global_state)
        first = self.scenario(Source("acoustic", 5, position_error=3), seed=1)
        second = self.scenario(Source("acoustic", 5, position_error=3), seed=2)
        self.assertNotEqual(first.source("s1").recent(), second.source("s1").recent())

    def test_empirical_rates_match_documented_probabilities(self):
        source = Source("acoustic", 5, sensitivity=0.8, false_negative_rate=0.25,
                        false_positive_rate=0.3)
        for kind, expected in (("threat", 0.6), ("thunder", 0.24)):
            with self.subTest(kind=kind):
                scenario = self.scenario(source, Event("e", kind, Position(0, 0), 0, 2000))
                for _ in range(1999):
                    scenario.advance()
                actual = len(scenario.ground_truth["observations"]) / 2000
                self.assertAlmostEqual(actual, expected, delta=0.04)

    def test_saved_run_can_be_replayed_and_is_not_overwritten(self):
        scenario = Scenario.from_config(CONFIG)
        for seconds in (0.5, 0.5, 1, 2, 5):
            scenario.advance(seconds)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            scenario.save_run(path)
            saved = json.loads(path.read_text())
            self.assertEqual(saved["config"]["scenario"]["seed"], 42)
            config = Path(directory) / "config.json"
            config.write_text(json.dumps(saved["config"]))
            replay = Scenario.from_config(config)
            for seconds in saved["steps"]:
                replay.advance(seconds)
            repeated = Path(directory) / "repeated.json"
            replay.save_run(repeated)
            self.assertEqual(saved, json.loads(repeated.read_text()))
            with self.assertRaises(FileExistsError):
                scenario.save_run(path)
            self.assertEqual(saved, json.loads(path.read_text()))

    def test_invalid_source_and_event_values_are_rejected(self):
        source = Source("acoustic", 5)
        for field in ("detection_range", "sensitivity", "false_positive_rate",
                      "false_negative_rate", "confidence", "position_error"):
            for value in (-1, True, "1", None, float("nan"), float("inf")):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    replace(source, **{field: value})
        for field in ("sensitivity", "false_positive_rate", "false_negative_rate", "confidence"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                replace(source, **{field: 1.01})
        with self.assertRaises(ValueError):
            replace(source, kind="radar")
        with self.assertRaises(ValueError):
            replace(source, position_error=0.5)
        with self.assertRaises(ValueError):
            replace(source, detection_range=10 ** 400)
        event = Event("e", "threat", Position(0, 0), 0, 10)
        for field in ("starts_at", "duration", "speed"):
            for value in (-1, True, "1", None, float("nan"), float("inf"), 10 ** 400):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    replace(event, **{field: value})
        for fields in ({"duration": 0}, {"event_id": " "}, {"kind": "unknown"},
                       {"starts_at": 1e308, "duration": 1e308}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                replace(event, **fields)
        with self.assertRaises(TypeError):
            replace(event, destination=(1, 2))
        for speed, elapsed in ((-1, 1), (1, -1), (True, 1), (1, float("nan"))):
            with self.assertRaises(ValueError):
                position_at(Position(0, 0), Position(1, 1), speed, elapsed)

    def test_invalid_config_and_scenario_are_rejected(self):
        original = json.loads(CONFIG.read_text())
        changes = [
            {"seed": True}, {"corroboration_window": -1}, {"sources": {}},
            {"sources": []}, {"events": {}}, {"extra": 1},
            {"events": [original["scenario"]["events"][0]] * 2},
            {"events": [dict(original["scenario"]["events"][0], destination={"x": 12, "y": 0})]},
            {"events": [dict(original["scenario"]["events"][0], position={"x": 12, "y": 0})]},
            {"events": [{}]}, {"events": [None]},
            {"sources": {"sensor_01": {"kind": "radar"}}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            for change in changes:
                with self.subTest(change=change):
                    data = dict(original, scenario=dict(original["scenario"], **change))
                    path.write_text(json.dumps(data))
                    with self.assertRaises(ValueError):
                        Scenario.from_config(path)
            path.write_text('{"width": 1, "width": 2}')
            with self.assertRaisesRegex(ValueError, "Chave repetida"):
                Scenario.from_config(path)

    def test_invalid_advance_preserves_observations_and_direct_clock_use_is_detected(self):
        scenario = self.scenario()
        observations = scenario.source("s1").recent()
        for seconds in (0, -1, True, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                scenario.advance(seconds)
            self.assertEqual(scenario.world.clock.now, 0)
            self.assertEqual(scenario.source("s1").recent(), observations)
        scenario.world.clock.advance()
        with self.assertRaisesRegex(ValueError, "scenario.advance"):
            scenario.advance()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                scenario.save_run(Path(directory) / "run.json")

    def test_cli_runs_without_xmpp_and_records_the_run(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run.json"
            result = subprocess.run(
                [sys.executable, "-m", "isia.simulation", str(CONFIG), "--steps", "3",
                 "--step-seconds", "0.5", "--output", str(output)],
                capture_output=True, text=True, check=True, cwd=ROOT)
            self.assertIn("obs-", result.stdout)
            self.assertNotIn("occurrence_01", result.stdout)
            saved = json.loads(output.read_text())
            self.assertEqual(saved["steps"], [0.5, 0.5, 0.5])
            self.assertEqual(saved["finished_at"], 1.5)
            self.assertEqual(len(saved["ground_truth"]["events"]), 1)


if __name__ == "__main__":
    unittest.main()

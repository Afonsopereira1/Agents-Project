"""Bloco G: configuração validada sem alterar a referência nem a aprendizagem."""

from copy import deepcopy
import inspect
from pathlib import Path
import unittest
from unittest.mock import patch

from isia.domain.models import Observation, Position
from isia.evaluation import collector
from isia.evaluation.metrics import run_metrics
from isia.reasoning.reputation import EvaluationResult
from isia.simulation import runner


ROOT = Path(__file__).resolve().parents[2]


class TestSensitivityParameterValidation(unittest.TestCase):
    def test_effective_defaults_and_published_conditions(self):
        self.assertEqual(runner.validate_experimental_settings(),
                         ({"max_distance": 3.0, "max_time_difference": 2.0}, 0.5, 10.0))
        self.assertEqual(runner.validate_experimental_settings(xmpp=True)[1], 2.0)
        defaults = inspect.signature(runner.run_mvp).parameters
        # Prazo dinâmico, fila e silêncio ligados por omissão (18-11-2026); o resto continua desligado.
        for key, value in {"extra_initiators": None, "extra_patrols": None, "cfp_limit": None,
                           "max_receive_timeout": 2.0, "queue_rounds": 60,
                           "silent_invalid": True, "queue_priority": False}.items():
            self.assertEqual(defaults[key].default, value)
        self.assertEqual(runner.PUBLISHED_CONDITIONS,
                         {"max_receive_timeout": None, "queue_rounds": 0, "silent_invalid": False})

    def test_allowlist_preserves_the_scenario_contract_and_blocks_stress_overrides(self):
        config = collector.load_scenario(ROOT / "config/scenarios/A.json")
        with self.assertRaises(ValueError):
            collector.validate_scenario({**config, "runner_options": {}})
        for invalid in (True, [], {"queue_rounds": 1}, {"max_receive_timeout": 2.0},
                        {"corroborate": False}, {"receive_timeout": 0}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                collector.validate_runner_options(invalid)

    def test_runner_options_are_independent_copies(self):
        original = {"corroboration_settings": {"max_distance": 1.0},
                    "selection_weights": {"eta_weight": 0.0, "load_weight": 0.0}}
        copy = collector.validate_runner_options(original)
        copy["corroboration_settings"]["max_distance"] = 5.0
        copy["selection_weights"]["eta_weight"] = 1.0
        self.assertEqual(original["corroboration_settings"]["max_distance"], 1.0)
        self.assertEqual(original["selection_weights"]["eta_weight"], 0.0)


class TestSensitivityRunner(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_original_values_repeat_the_default_metrics(self):
        config = collector.load_scenario(ROOT / "config/scenarios/A.json")
        scenario = {"run_id": "reference", "seed": 1000, "sources": config["sources"],
                    "events": config["episodes"][0]["events"], "resources": config["resources"]}
        default = await runner.run_mvp(response_settings=config["response_settings"], scenario=scenario)
        explicit = await runner.run_mvp(
            response_settings=config["response_settings"], scenario=scenario,
            corroboration_settings={"max_distance": 3.0, "max_time_difference": 2.0},
            receive_timeout=0.5, minimum_autonomy_percent=10.0,
            selection_weights={"eta_weight": 1.0, "energy_weight": 1.0, "load_weight": 1.0})
        self.assertEqual(run_metrics(default), run_metrics(explicit))
        self.assertEqual(default["incident_status"], "closed")
        self.assertEqual(default["corroboration_settings"],
                         {"max_distance": 3.0, "max_time_difference": 2.0})
        self.assertEqual((default["receive_timeout"], default["minimum_autonomy_percent"]), (0.5, 10.0))

    async def test_overrides_reach_agents_and_coexist_with_stress_options(self):
        sensors, mobiles = [], []

        def capture(cls, destination):
            def create(*args, **kwargs):
                agent = cls(*args, **kwargs)
                destination.append(agent)
                return agent
            return create

        weights = {"eta_weight": 0.0, "energy_weight": 1.0, "load_weight": 0.0}
        with patch.object(runner, "IncidentSensorAgent", side_effect=capture(runner.IncidentSensorAgent, sensors)), \
                patch.object(runner, "DroneAgent", side_effect=capture(runner.DroneAgent, mobiles)), \
                patch.object(runner, "VehicleAgent", side_effect=capture(runner.VehicleAgent, mobiles)), \
                patch.object(runner, "RangerAgent", side_effect=capture(runner.RangerAgent, mobiles)):
            report = await runner.run_mvp(
                corroboration_settings={"max_distance": 1.0, "max_time_difference": 0.5},
                receive_timeout=0.1, minimum_autonomy_percent=30.0, selection_weights=weights,
                extra_patrols={"extra-drone": Position(7, 7)}, cfp_limit=1,
                max_receive_timeout=0.2, queue_rounds=1, silent_invalid=True, queue_priority=True)
        [sensor] = sensors
        self.assertEqual((sensor.max_distance, sensor.max_time_difference), (1.0, 0.5))
        self.assertEqual(sensor.minimum_compatible_sources, 1)
        self.assertEqual((sensor.receive_timeout, sensor.max_receive_timeout), (0.1, 0.2))
        self.assertEqual((sensor.queue_rounds, sensor.cfp_limit), (1, 1))
        self.assertEqual(sensor.selection_weights, weights)
        self.assertEqual(len(mobiles), 4)
        self.assertTrue(all(agent.minimum_autonomy_percent == 30.0 for agent in mobiles))
        self.assertTrue(all(agent.silent_invalid and agent.ordered_queue for agent in mobiles))
        self.assertEqual(report["incident_status"], "closed")

    async def test_invalid_parameters_are_rejected_before_agent_creation(self):
        invalid = [
            {"corroboration_settings": []}, {"corroboration_settings": {"unknown": 1}},
            *({"corroboration_settings": {name: value}}
              for name in ("max_distance", "max_time_difference")
              for value in (-1, True, float("nan"), float("inf"), "1")),
            *({"receive_timeout": value} for value in (0, -1, False, float("nan"), float("inf"))),
            *({"minimum_autonomy_percent": value} for value in (-1, 101, True, float("nan"))),
            {"selection_weights": {"eta_weight": -1}}, {"selection_weights": {"extra": 1}},
            {"selection_weights": {"load_scale": 0}},
            {"selection_weights": {"eta_weight": 0, "energy_weight": 0, "load_weight": 0}},
        ]
        with patch.object(runner, "IncidentSensorAgent") as sensor:
            for options in invalid:
                with self.subTest(options=options), self.assertRaises(ValueError):
                    await runner.run_mvp(**options)
            sensor.assert_not_called()


class TestSensitivityCollector(unittest.IsolatedAsyncioTestCase):
    async def test_longer_base_timeout_uses_runner_watchdog_without_changing_reference(self):
        config = collector.load_scenario(ROOT / "config/scenarios/A.json")
        for options, expected in ((None, 30.0), ({"receive_timeout": 0.1}, 30.0),
                                  ({"receive_timeout": 0.5}, 30.0), ({"receive_timeout": 2.0}, None)):
            with self.subTest(options=options), \
                    patch.object(collector, "run_mvp", return_value={}) as simulate, \
                    patch.object(collector, "run_metrics", return_value={}):
                await collector.run_scenario(config, "full", repetitions=1, runner_options=options)
                self.assertTrue(all(call.kwargs["max_seconds"] == expected for call in simulate.call_args_list))

    async def test_full_retains_reputation_in_episode_and_repetition_order(self):
        config = collector.load_scenario(ROOT / "config/scenarios/A.json")
        before = deepcopy(config)
        books, ids, seeds = [], [], []

        async def simulate(**kwargs):
            book, scenario = kwargs["reputation"], kwargs["scenario"]
            books.append(book)
            ids.append(scenario["run_id"])
            seeds.append(scenario["seed"])
            observation = Observation("obs", "sensor-1", "gunshot_like_sound", Position(1, 1), 0, 0.8)
            reference = EvaluationResult(
                "result", "incident", ("obs",), "confirmed", "independent_mission", 1,
                evidence_ids=("inspection",), evidence_source_ids=("patrol",),
                final=True, sufficient_coverage=True)
            book.update(observation, "incident", reference, run_id=scenario["run_id"])
            self.assertEqual(kwargs["receive_timeout"], 0.1)
            # O Bloco G corre nas condições publicadas, não com as opções ligadas por omissão.
            self.assertEqual({key: kwargs[key] for key in runner.PUBLISHED_CONDITIONS},
                             runner.PUBLISHED_CONDITIONS)
            return {}

        with patch.object(collector, "run_mvp", side_effect=simulate), \
                patch.object(collector, "run_metrics", return_value={}):
            rows = await collector.run_scenario(config, "full", repetitions=2,
                                                runner_options={"receive_timeout": 0.1})
        self.assertEqual(len({id(book) for book in books}), 1)
        self.assertEqual(ids, ["A-full-000-threat", "A-full-000-empty", "A-full-001-threat", "A-full-001-empty"])
        self.assertEqual(seeds, [1000, 1000, 1001, 1001])
        self.assertEqual([row["reputation_sensor_1"] for row in rows], [3/5, 4/6, 5/7, 6/8])
        self.assertEqual(config, before)

    async def test_options_reach_runner_without_mutation_or_variant_ambiguity(self):
        config = collector.load_scenario(ROOT / "config/scenarios/A.json")
        options = {"corroboration_settings": {"max_distance": 1.0},
                   "minimum_autonomy_percent": 5.0,
                   "selection_weights": {"eta_weight": 0.0, "load_weight": 0.0}}
        original = deepcopy(options)
        distances = []

        async def simulate(**kwargs):
            distances.append(kwargs["corroboration_settings"]["max_distance"])
            self.assertEqual(kwargs["minimum_autonomy_percent"], 5.0)
            self.assertEqual(kwargs["selection_weights"], options["selection_weights"])
            kwargs["corroboration_settings"]["max_distance"] = 99
            return {}

        with patch.object(collector, "run_mvp", side_effect=simulate), \
                patch.object(collector, "run_metrics", return_value={}):
            await collector.run_scenario(config, "full", repetitions=1, runner_options=options)
        self.assertEqual(distances, [1.0, 1.0])
        self.assertEqual(options, original)
        with self.assertRaisesRegex(ValueError, "incompatível"):
            await collector.run_scenario(config, "nearest", repetitions=1, runner_options=options)


if __name__ == "__main__":
    unittest.main()

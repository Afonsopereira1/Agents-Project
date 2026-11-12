"""Etapa 9: cenários versionados, repetição controlada e armazenamento."""

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

try:
    from isia.evaluation.collector import VARIANTS, load_scenario, run_scenario
    from isia.simulation.runner import run_mvp
except ImportError:
    run_mvp = None


ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = sorted((ROOT / "config/scenarios").glob("*.json"))


@unittest.skipUnless(run_mvp, "SPADE não está instalado")
class TestExperiments(unittest.IsolatedAsyncioTestCase):
    def test_three_versioned_scenarios_load(self):
        self.assertEqual([load_scenario(p)["scenario_id"] for p in SCENARIOS], ["A", "B", "C"])

    async def test_same_seed_repeats_same_metrics_and_stores_runs(self):
        config = load_scenario(ROOT / "config/scenarios/A.json")
        with TemporaryDirectory() as output:
            first = await run_scenario(config, "full", repetitions=1, output=output)
            second = await run_scenario(config, "full", repetitions=1)
            self.assertEqual(first, second)
            stored = sorted(Path(output, "A", "full").glob("*.json"))
            self.assertEqual([p.stem for p in stored], ["A-full-000-empty", "A-full-000-threat"])
            data = json.loads(stored[1].read_text())
            self.assertEqual(data["metrics"]["seed"], 1000)
            self.assertIn("ground_truth", data["report"])

    async def test_empty_episode_never_dispatches(self):
        config = load_scenario(ROOT / "config/scenarios/A.json")
        config["episodes"] = [{"label": "empty", "events": []}]
        for variant in VARIANTS:
            [row] = await run_scenario(config, variant, repetitions=1)
            self.assertEqual((row["threat"], row["alert"], row["dispatched"]), (False, False, False))

    async def test_nearest_picks_drone_while_cost_avoids_loaded_drone(self):
        config = load_scenario(ROOT / "config/scenarios/A.json")
        config["episodes"] = config["episodes"][:1]
        config["base_seed"] = 1000  # Esta semente produz alerta corroborado.
        [cost] = await run_scenario(config, "full", repetitions=1)
        [nearest] = await run_scenario(config, "nearest", repetitions=1)
        self.assertEqual((cost["first_patrol"], nearest["first_patrol"]), ("vehicle", "drone"))

    async def test_scenario_validation(self):
        with self.assertRaises(ValueError):
            await run_mvp(scenario={"seed": 1})
        config = load_scenario(ROOT / "config/scenarios/A.json")
        late = {**config["episodes"][0]["events"][0], "starts_at": 2.0}
        with self.assertRaisesRegex(ValueError, "t=0"):
            await run_mvp(scenario={"run_id": "late", "seed": 1, "sources": config["sources"],
                                    "events": [late], "resources": {}})

    def test_empty_episodes_are_rejected(self):
        config = load_scenario(ROOT / "config/scenarios/A.json")
        with TemporaryDirectory() as directory:
            path = Path(directory, "empty.json")
            path.write_text(json.dumps({**config, "episodes": []}))
            with self.assertRaisesRegex(ValueError, "episodes"):
                load_scenario(path)


if __name__ == "__main__":
    unittest.main()

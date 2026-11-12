from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]


class TestGitignore(unittest.TestCase):
    def ignored(self, path):
        result = subprocess.run(
            ["git", "-c", "core.excludesFile=/dev/null", "check-ignore",
             "--no-index", "-q", "--", path],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return result.returncode == 0

    def test_new_agent_source_is_not_ignored(self):
        self.assertFalse(self.ignored("src/isia/agents/new_agent.py"))

    def test_virtual_environments_remain_ignored(self):
        for path in ("agents/bin/python", ".venv/bin/python", "venv/bin/python",
                     "spade_venv/bin/python"):
            with self.subTest(path=path):
                self.assertTrue(self.ignored(path))

"""Opt-in real-scene smoke test for the Stage 2 Habitat pipeline."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from navida_habitat.episode_runner import EpisodeRunner
from navida_habitat.habitat_env import HabitatEnvAdapter
from navida_habitat.mock_backend import MockBackend


RUN_INTEGRATION = os.environ.get("NAVIDA_HABITAT_RUN_INTEGRATION") == "1"
SCENE_PATH = os.environ.get("NAVIDA_HABITAT_SCENE")


@unittest.skipUnless(
    RUN_INTEGRATION and SCENE_PATH,
    "set NAVIDA_HABITAT_RUN_INTEGRATION=1 and NAVIDA_HABITAT_SCENE",
)
class HabitatRealSceneSmokeTests(unittest.TestCase):
    def test_mock_backend_runs_through_real_scene_and_jsonl(self) -> None:
        scene_path = Path(SCENE_PATH or "")
        self.assertTrue(scene_path.is_file())

        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "stage2-smoke.jsonl"
            environment = HabitatEnvAdapter(scene_path=scene_path)
            with environment:
                initial_position = dict(environment.position)
                initial_yaw = environment.rotation_yaw
                runner = EpisodeRunner(
                    backend=MockBackend(
                        ["forward 50 cm, turn left 30 degree", "stop"]
                    ),
                    environment=environment,
                    max_steps=10,
                    log_path=log_path,
                )
                summary = runner.run(
                    episode_id="stage2-integration",
                    instruction="Walk forward and turn left.",
                )
                final_position = dict(environment.position)
                final_yaw = environment.rotation_yaw
                rgb_observation = environment.rgb_observation

            entries = [
                json.loads(line)
                for line in log_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertTrue(environment.closed)
        self.assertEqual(summary.termination_reason, "stop")
        self.assertTrue(summary.done)
        self.assertFalse(summary.success)
        self.assertEqual(len(entries), 2)
        self.assertEqual(
            entries[0]["executed_actions"],
            ["move_forward", "move_forward", "turn_left", "turn_left"],
        )
        self.assertEqual(entries[1]["executed_actions"], ["stop"])
        self.assertEqual(entries[1]["position"], final_position)
        self.assertAlmostEqual(entries[1]["rotation_yaw"], final_yaw)
        self.assertEqual(entries[1]["termination"], "stop")
        self.assertFalse(entries[1]["success"])
        self.assertEqual(rgb_observation.shape[-1], 4)
        self.assertEqual(str(rgb_observation.dtype), "uint8")
        self.assertNotEqual(initial_position, final_position)
        self.assertAlmostEqual(
            (final_yaw - initial_yaw + 180.0) % 360.0 - 180.0,
            30.0,
            delta=0.05,
        )


if __name__ == "__main__":
    unittest.main()

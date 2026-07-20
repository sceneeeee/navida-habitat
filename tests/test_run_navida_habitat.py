"""Tests for the formal NaVIDA-Habitat command-line runner."""

from __future__ import annotations

import json
import runpy
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from navida_habitat.action_chunk import HabitatAction
from navida_habitat.model_runtime import NaVIDAGenerationResult


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "run_navida_habitat.py"
)

SCRIPT = runpy.run_path(
    str(SCRIPT_PATH),
    run_name="run_navida_habitat_test",
)

parse_args = SCRIPT["parse_args"]
run = SCRIPT["run"]


def rgba(
    red: int,
    green: int,
    blue: int,
) -> Image.Image:
    """Create one opaque RGBA observation."""

    return Image.new(
        "RGBA",
        (16, 16),
        (red, green, blue, 255),
    )


class FakeEnvironment:
    """Small environment used to test CLI orchestration."""

    def __init__(self, *, scene_path: Path) -> None:
        self.scene_path = scene_path
        self._position = {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
        }
        self._yaw = 0.0
        self._done = False
        self._closed = False
        self._observation = rgba(255, 0, 0)

    @property
    def position(self) -> dict[str, float]:
        return dict(self._position)

    @property
    def rotation_yaw(self) -> float:
        return self._yaw

    @property
    def rgb_observation(self) -> Image.Image:
        return self._observation

    @property
    def done(self) -> bool:
        return self._done

    @property
    def success(self) -> bool:
        return False

    @property
    def closed(self) -> bool:
        return self._closed

    def execute(self, action: HabitatAction) -> None:
        """Apply one deterministic fake action."""

        if action is HabitatAction.MOVE_FORWARD:
            self._position["z"] += 0.25
            self._observation = rgba(0, 255, 0)
        elif action is HabitatAction.TURN_LEFT:
            self._yaw += 15.0
            self._observation = rgba(0, 0, 255)
        elif action is HabitatAction.TURN_RIGHT:
            self._yaw -= 15.0
            self._observation = rgba(255, 255, 0)
        elif action is HabitatAction.STOP:
            self._done = True

    def close(self) -> None:
        """Close the fake environment."""

        self._closed = True

    def __enter__(self) -> FakeEnvironment:
        return self

    def __exit__(
        self,
        exception_type: object,
        exception: object,
        traceback: object,
    ) -> None:
        del exception_type, exception, traceback
        self.close()


class FakeRuntime:
    """Return one movement decision followed by STOP."""

    instances: list[FakeRuntime] = []

    def __init__(
        self,
        model_path: Path,
        *,
        settings: object,
    ) -> None:
        self.model_path = model_path
        self.settings = settings
        self.outputs = [
            "forward 25 cm",
            "stop",
        ]
        self.history_lengths: list[int] = []
        self.load_calls = 0
        self._loaded = False
        type(self).instances.append(self)

    @property
    def loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        self.load_calls += 1
        self._loaded = True

    def generate(
        self,
        *,
        instruction: str,
        history_images: tuple[Image.Image, ...],
        current_image: Image.Image,
    ) -> NaVIDAGenerationResult:
        del instruction, current_image

        self.history_lengths.append(len(history_images))
        output = self.outputs.pop(0)

        return NaVIDAGenerationResult(
            raw_output=output,
            input_token_count=100,
            generated_token_count=4,
            latency_seconds=0.1,
            peak_allocated_gib=1.0,
            peak_reserved_gib=1.2,
        )


class RunNaVIDAHabitatTest(unittest.TestCase):
    """Test CLI validation and two-decision orchestration."""

    def setUp(self) -> None:
        FakeRuntime.instances.clear()

    def test_rejects_non_positive_max_steps(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(
                [
                    "--scene-path",
                    "scene.glb",
                    "--model-path",
                    "model",
                    "--instruction",
                    "Walk forward.",
                    "--output-dir",
                    "output",
                    "--max-steps",
                    "0",
                ]
            )

    def test_runs_two_decisions_and_writes_artifacts(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            scene_path = root / "scene.glb"
            model_path = root / "model"
            output_dir = root / "output"

            scene_path.write_bytes(b"fake scene")
            model_path.mkdir()

            args = parse_args(
                [
                    "--scene-path",
                    str(scene_path),
                    "--model-path",
                    str(model_path),
                    "--instruction",
                    "Walk forward and stop.",
                    "--output-dir",
                    str(output_dir),
                    "--episode-id",
                    "cli-test",
                    "--max-steps",
                    "2",
                ]
            )

            payload = run(
                args,
                environment_factory=FakeEnvironment,
                runtime_factory=FakeRuntime,
            )

            runtime = FakeRuntime.instances[-1]

            self.assertEqual(runtime.load_calls, 1)
            self.assertEqual(runtime.history_lengths, [0, 1])

            episode = payload["episode"]
            self.assertEqual(episode["steps"], 2)
            self.assertEqual(
                episode["termination_reason"],
                "stop",
            )

            decisions = payload["decisions"]
            self.assertEqual(len(decisions), 2)
            self.assertEqual(
                decisions[0]["sampled_history_count"],
                0,
            )
            self.assertEqual(
                decisions[1]["sampled_history_count"],
                1,
            )

            self.assertTrue(payload["simulator_closed"])

            self.assertTrue(
                (output_dir / "episode.jsonl").is_file()
            )
            self.assertTrue(
                (output_dir / "summary.json").is_file()
            )
            self.assertTrue(
                (output_dir / "initial_rgb.png").is_file()
            )
            self.assertTrue(
                (output_dir / "final_rgb.png").is_file()
            )

            log_lines = (
                output_dir / "episode.jsonl"
            ).read_text(encoding="utf-8").splitlines()

            self.assertEqual(len(log_lines), 2)

            saved_summary = json.loads(
                (output_dir / "summary.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                saved_summary["episode"]["episode_id"],
                "cli-test",
            )


if __name__ == "__main__":
    unittest.main()

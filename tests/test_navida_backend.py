"""Tests for NaVIDA history sampling and Habitat observation capture."""

from __future__ import annotations

import unittest

import numpy as np
from PIL import Image

from navida_habitat.action_chunk import HabitatAction
from navida_habitat.episode_runner import EpisodeRunner
from navida_habitat.frame_history import (
    FrameHistory,
    uniform_sample_with_ends,
)
from navida_habitat.model_runtime import NaVIDAGenerationResult
from navida_habitat.navida_backend import NaVIDABackend


def solid_rgba(
    red: int,
    green: int,
    blue: int,
) -> np.ndarray:
    """Create one small opaque RGBA observation."""

    observation = np.zeros((12, 16, 4), dtype=np.uint8)
    observation[:, :, 0] = red
    observation[:, :, 1] = green
    observation[:, :, 2] = blue
    observation[:, :, 3] = 255
    return observation


class FakeObservationProvider:
    def __init__(self, observation: np.ndarray) -> None:
        self.rgb_observation = observation


class FakeRuntime:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate(
        self,
        *,
        instruction: str,
        history_images: tuple[Image.Image, ...],
        current_image: Image.Image,
    ) -> NaVIDAGenerationResult:
        self.calls.append(
            {
                "instruction": instruction,
                "history": tuple(
                    image.copy()
                    for image in history_images
                ),
                "current": current_image.copy(),
            }
        )

        return NaVIDAGenerationResult(
            raw_output="forward 25 cm",
            input_token_count=0,
            generated_token_count=0,
            latency_seconds=0.0,
            peak_allocated_gib=0.0,
            peak_reserved_gib=0.0,
        )


class ObservingBackend:
    def __init__(self) -> None:
        self.observe_calls = 0

    def infer(self, *, instruction: str, step: int) -> str:
        del instruction, step
        return "forward 50 cm, stop"

    def observe(self) -> None:
        self.observe_calls += 1


class MinimalEnvironment:
    def __init__(self) -> None:
        self.actions: list[HabitatAction] = []
        self._done = False

    @property
    def position(self) -> dict[str, float]:
        return {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
        }

    @property
    def rotation_yaw(self) -> float:
        return 0.0

    @property
    def done(self) -> bool:
        return self._done

    @property
    def success(self) -> bool:
        return False

    def execute(self, action: HabitatAction) -> None:
        self.actions.append(action)

        if action is HabitatAction.STOP:
            self._done = True


class FrameHistoryTest(unittest.TestCase):
    def test_uniform_sampling_preserves_ends(self) -> None:
        sampled = uniform_sample_with_ends(
            tuple(range(11)),
            4,
        )

        self.assertEqual(sampled, (0, 3, 7, 10))

    def test_history_is_bounded(self) -> None:
        history = FrameHistory(
            max_stored_frames=3,
            sample_count=2,
        )

        for value in range(5):
            history.append(
                Image.new(
                    "RGB",
                    (2, 2),
                    (value, 0, 0),
                )
            )

        self.assertEqual(len(history), 3)
        self.assertEqual(
            history.latest.getpixel((0, 0)),
            (4, 0, 0),
        )


class NaVIDABackendTest(unittest.TestCase):
    def test_first_step_uses_current_without_history(self) -> None:
        provider = FakeObservationProvider(
            solid_rgba(255, 0, 0)
        )
        runtime = FakeRuntime()
        backend = NaVIDABackend(
            runtime=runtime,
            observation_provider=provider,
        )

        output = backend.infer(
            instruction="Walk forward.",
            step=0,
        )

        self.assertEqual(output, "forward 25 cm")
        self.assertEqual(len(runtime.calls), 1)
        self.assertEqual(len(backend.frame_history), 1)

        call = runtime.calls[0]
        history = call["history"]
        current = call["current"]

        self.assertEqual(history, ())
        self.assertIsInstance(current, Image.Image)
        self.assertEqual(current.mode, "RGB")
        self.assertEqual(current.size, (308, 252))
        self.assertEqual(
            current.getpixel((0, 0)),
            (255, 0, 0),
        )

    def test_records_intermediate_action_observations(self) -> None:
        provider = FakeObservationProvider(
            solid_rgba(255, 0, 0)
        )
        runtime = FakeRuntime()
        backend = NaVIDABackend(
            runtime=runtime,
            observation_provider=provider,
        )

        backend.infer(
            instruction="Continue.",
            step=0,
        )

        provider.rgb_observation = solid_rgba(0, 255, 0)
        backend.observe()

        provider.rgb_observation = solid_rgba(0, 0, 255)
        backend.observe()

        backend.infer(
            instruction="Continue.",
            step=1,
        )

        call = runtime.calls[1]
        history = call["history"]
        current = call["current"]

        self.assertEqual(len(history), 2)
        self.assertEqual(
            history[0].getpixel((0, 0)),
            (255, 0, 0),
        )
        self.assertEqual(
            history[1].getpixel((0, 0)),
            (0, 255, 0),
        )
        self.assertEqual(
            current.getpixel((0, 0)),
            (0, 0, 255),
        )

    def test_step_zero_resets_previous_episode(self) -> None:
        provider = FakeObservationProvider(
            solid_rgba(255, 0, 0)
        )
        runtime = FakeRuntime()
        backend = NaVIDABackend(
            runtime=runtime,
            observation_provider=provider,
        )

        backend.infer(
            instruction="First episode.",
            step=0,
        )

        provider.rgb_observation = solid_rgba(0, 255, 0)
        backend.observe()

        provider.rgb_observation = solid_rgba(0, 0, 255)
        backend.infer(
            instruction="Second episode.",
            step=0,
        )

        call = runtime.calls[1]

        self.assertEqual(call["history"], ())
        self.assertEqual(len(backend.frame_history), 1)
        self.assertEqual(
            call["current"].getpixel((0, 0)),
            (0, 0, 255),
        )


class EpisodeObservationHookTest(unittest.TestCase):
    def test_runner_observes_after_every_atomic_action(self) -> None:
        backend = ObservingBackend()
        environment = MinimalEnvironment()

        summary = EpisodeRunner(
            backend=backend,
            environment=environment,
            max_steps=1,
        ).run(
            episode_id="observation-hook",
            instruction="Move and stop.",
        )

        self.assertEqual(
            environment.actions,
            [
                HabitatAction.MOVE_FORWARD,
                HabitatAction.MOVE_FORWARD,
                HabitatAction.STOP,
            ],
        )
        self.assertEqual(backend.observe_calls, 3)
        self.assertEqual(summary.termination_reason, "stop")


if __name__ == "__main__":
    unittest.main()

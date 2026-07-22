"""Tests for the evaluator-facing Official NaVIDA policy API."""

from __future__ import annotations

import json
import unittest
from collections.abc import Sequence

import numpy as np
from PIL import Image

import navida_habitat
from navida_habitat.action_chunk import ActionKind, HabitatAction
from navida_habitat.model_runtime import NaVIDAGenerationResult
from navida_habitat.policy import NaVIDAPolicyDecision, OfficialNaVIDAPolicy


def solid_rgba(red: int, green: int, blue: int) -> np.ndarray:
    """Create one small opaque RGBA observation."""

    observation = np.zeros((12, 16, 4), dtype=np.uint8)
    observation[:, :, 0] = red
    observation[:, :, 1] = green
    observation[:, :, 2] = blue
    observation[:, :, 3] = 255
    return observation


class FakeRuntime:
    def __init__(self, outputs: Sequence[str]) -> None:
        self.outputs = tuple(outputs)
        self.calls: list[dict[str, object]] = []

    def generate(
        self,
        *,
        instruction: str,
        history_images: Sequence[Image.Image],
        current_image: Image.Image,
    ) -> NaVIDAGenerationResult:
        self.calls.append(
            {
                "instruction": instruction,
                "history": tuple(image.copy() for image in history_images),
                "current": current_image.copy(),
            }
        )
        return NaVIDAGenerationResult(
            raw_output=self.outputs[len(self.calls) - 1],
            input_token_count=101,
            generated_token_count=7,
            latency_seconds=0.25,
            peak_allocated_gib=1.5,
            peak_reserved_gib=2.0,
        )


class ClosableFakeRuntime(FakeRuntime):
    def __init__(self, outputs: Sequence[str]) -> None:
        super().__init__(outputs)
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


class OfficialNaVIDAPolicyTest(unittest.TestCase):
    def test_policy_types_are_exported_from_the_package(self) -> None:
        self.assertIs(
            navida_habitat.OfficialNaVIDAPolicy,
            OfficialNaVIDAPolicy,
        )
        self.assertIs(
            navida_habitat.NaVIDAPolicyDecision,
            NaVIDAPolicyDecision,
        )

    def test_official_repro_protocol_is_explicitly_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "paper_pure"):
            OfficialNaVIDAPolicy(
                runtime=FakeRuntime(["stop"]),
                protocol="official_repro",
            )

    def test_first_decision_uses_observed_rgb_without_history(self) -> None:
        runtime = FakeRuntime(["forward 25 cm"])
        policy = OfficialNaVIDAPolicy(runtime=runtime)

        policy.reset("episode-1")
        policy.observe(solid_rgba(255, 0, 0))
        decision = policy.act(
            instruction="Walk through the doorway.",
            decision_step=0,
        )

        self.assertTrue(decision.valid)
        self.assertEqual(decision.episode_id, "episode-1")
        self.assertEqual(
            decision.atomic_actions,
            (HabitatAction.MOVE_FORWARD,),
        )
        self.assertEqual(len(runtime.calls), 1)
        self.assertEqual(runtime.calls[0]["history"], ())
        current = runtime.calls[0]["current"]
        self.assertIsInstance(current, Image.Image)
        self.assertEqual(current.mode, "RGB")
        self.assertEqual(current.size, (308, 252))
        self.assertEqual(current.getpixel((0, 0)), (255, 0, 0))

    def test_observe_keeps_an_independent_rgb_snapshot(self) -> None:
        runtime = FakeRuntime(["stop"])
        policy = OfficialNaVIDAPolicy(runtime=runtime)
        observation = solid_rgba(255, 0, 0)
        policy.reset("snapshot")

        policy.observe(observation)
        observation[:, :, :3] = (0, 255, 0)
        policy.act(instruction="Stop.", decision_step=0)

        current = runtime.calls[0]["current"]
        self.assertEqual(current.getpixel((0, 0)), (255, 0, 0))

    def test_observations_after_actions_feed_the_next_decision(self) -> None:
        runtime = FakeRuntime(["forward 25 cm", "turn left 15 degree"])
        policy = OfficialNaVIDAPolicy(runtime=runtime)
        policy.reset("episode-1")
        policy.observe(solid_rgba(255, 0, 0))
        policy.act(instruction="Continue.", decision_step=0)

        policy.observe(Image.new("RGB", (4, 4), (0, 255, 0)))
        policy.observe(solid_rgba(0, 0, 255))
        decision = policy.act(instruction="Continue.", decision_step=1)

        history = runtime.calls[1]["history"]
        current = runtime.calls[1]["current"]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].getpixel((0, 0)), (255, 0, 0))
        self.assertEqual(history[1].getpixel((0, 0)), (0, 255, 0))
        self.assertEqual(current.getpixel((0, 0)), (0, 0, 255))
        self.assertEqual(decision.metadata["stored_frame_count"], 3)
        self.assertEqual(decision.metadata["available_history_count"], 2)
        self.assertEqual(decision.metadata["sampled_history_count"], 2)

    def test_reset_starts_new_history_without_replacing_runtime(self) -> None:
        runtime = FakeRuntime(["forward 25 cm", "stop"])
        policy = OfficialNaVIDAPolicy(runtime=runtime)
        policy.reset("episode-1")
        policy.observe(solid_rgba(255, 0, 0))
        policy.act(instruction="First episode.", decision_step=0)
        policy.observe(solid_rgba(0, 255, 0))

        policy.reset("episode-2")
        policy.observe(solid_rgba(0, 0, 255))
        decision = policy.act(instruction="Second episode.", decision_step=0)

        self.assertEqual(decision.episode_id, "episode-2")
        self.assertEqual(runtime.calls[1]["history"], ())
        self.assertEqual(
            runtime.calls[1]["current"].getpixel((0, 0)),
            (0, 0, 255),
        )
        self.assertEqual(decision.metadata["stored_frame_count"], 1)
        self.assertEqual(len(runtime.calls), 2)

    def test_invalid_output_is_returned_without_fallback_actions(self) -> None:
        raw_output = "forward 25 cm because the path is clear"
        policy = OfficialNaVIDAPolicy(runtime=FakeRuntime([raw_output]))
        policy.reset("invalid-output")
        policy.observe(solid_rgba(255, 0, 0))

        decision = policy.act(
            instruction="Walk forward.",
            decision_step=0,
        )

        self.assertFalse(decision.valid)
        self.assertEqual(decision.raw_output, raw_output)
        self.assertEqual(decision.parsed_sub_chunks, ())
        self.assertEqual(decision.atomic_actions, ())
        self.assertIsNotNone(decision.error)
        self.assertIn("action chunk grammar", decision.error or "")

    def test_invalid_output_still_advances_the_expected_step(self) -> None:
        runtime = FakeRuntime(
            [
                "forward 25 cm because the path is clear",
                "stop",
            ]
        )
        policy = OfficialNaVIDAPolicy(runtime=runtime)
        policy.reset("invalid-then-valid")
        policy.observe(solid_rgba(255, 0, 0))

        invalid_decision = policy.act(
            instruction="Walk forward.",
            decision_step=0,
        )
        policy.observe(solid_rgba(0, 255, 0))
        valid_decision = policy.act(
            instruction="Stop.",
            decision_step=1,
        )

        self.assertFalse(invalid_decision.valid)
        self.assertTrue(valid_decision.valid)
        self.assertEqual(len(runtime.calls), 2)

    def test_valid_chunk_preserves_parsing_and_expands_only_two_sub_chunks(
        self,
    ) -> None:
        policy = OfficialNaVIDAPolicy(
            runtime=FakeRuntime(
                [
                    "forward 50 cm, turn right 30 degree, "
                    "turn left 15 degree"
                ]
            )
        )
        policy.reset("bounded-expansion")
        policy.observe(solid_rgba(255, 0, 0))

        decision = policy.act(instruction="Navigate.", decision_step=0)

        self.assertTrue(decision.valid)
        self.assertEqual(
            tuple(
                (sub_chunk.kind, sub_chunk.amount)
                for sub_chunk in decision.parsed_sub_chunks
            ),
            (
                (ActionKind.FORWARD, 50),
                (ActionKind.TURN_RIGHT, 30),
                (ActionKind.TURN_LEFT, 15),
            ),
        )
        self.assertEqual(
            decision.atomic_actions,
            (
                HabitatAction.MOVE_FORWARD,
                HabitatAction.MOVE_FORWARD,
                HabitatAction.TURN_RIGHT,
                HabitatAction.TURN_RIGHT,
            ),
        )
        self.assertEqual(
            decision.metadata["parsed_sub_chunks"],
            [
                {"kind": "forward", "amount": 50},
                {"kind": "turn_right", "amount": 30},
                {"kind": "turn_left", "amount": 15},
            ],
        )
        self.assertEqual(decision.metadata["parsed_sub_chunk_count"], 3)
        self.assertEqual(decision.metadata["max_executed_sub_chunks"], 2)
        self.assertEqual(decision.metadata["executed_sub_chunk_count"], 2)
        self.assertEqual(decision.metadata["ignored_sub_chunk_count"], 1)
        self.assertEqual(
            decision.metadata["atomic_actions"],
            [
                "move_forward",
                "move_forward",
                "turn_right",
                "turn_right",
            ],
        )
        self.assertEqual(decision.metadata["atomic_action_count"], 4)

    def test_stop_is_preserved_in_atomic_actions(self) -> None:
        policy = OfficialNaVIDAPolicy(
            runtime=FakeRuntime(["forward 25 cm, stop"])
        )
        policy.reset("stop")
        policy.observe(solid_rgba(255, 0, 0))

        decision = policy.act(instruction="Stop there.", decision_step=0)

        self.assertEqual(
            decision.atomic_actions,
            (HabitatAction.MOVE_FORWARD, HabitatAction.STOP),
        )

    def test_act_before_reset_reports_required_lifecycle_call(self) -> None:
        policy = OfficialNaVIDAPolicy(runtime=FakeRuntime(["stop"]))

        with self.assertRaisesRegex(RuntimeError, r"reset\(episode_id\)"):
            policy.act(instruction="Stop.", decision_step=0)

    def test_observe_before_reset_reports_required_lifecycle_call(self) -> None:
        policy = OfficialNaVIDAPolicy(runtime=FakeRuntime(["stop"]))

        with self.assertRaisesRegex(RuntimeError, r"reset\(episode_id\)"):
            policy.observe(solid_rgba(255, 0, 0))

    def test_act_before_observe_reports_required_lifecycle_call(self) -> None:
        policy = OfficialNaVIDAPolicy(runtime=FakeRuntime(["stop"]))
        policy.reset("missing-observation")

        with self.assertRaisesRegex(RuntimeError, r"observe\(rgb\)"):
            policy.act(instruction="Stop.", decision_step=0)

    def test_reset_rejects_empty_episode_id(self) -> None:
        policy = OfficialNaVIDAPolicy(runtime=FakeRuntime(["stop"]))

        for episode_id in ("", "   "):
            with self.subTest(episode_id=episode_id):
                with self.assertRaisesRegex(ValueError, "episode_id"):
                    policy.reset(episode_id)

    def test_act_rejects_negative_decision_step(self) -> None:
        policy = OfficialNaVIDAPolicy(runtime=FakeRuntime(["stop"]))
        policy.reset("negative-step")
        policy.observe(solid_rgba(255, 0, 0))

        with self.assertRaisesRegex(ValueError, "decision_step"):
            policy.act(instruction="Stop.", decision_step=-1)

    def test_act_rejects_repeated_decision_step_zero(self) -> None:
        runtime = FakeRuntime(["forward 25 cm", "stop"])
        policy = OfficialNaVIDAPolicy(runtime=runtime)
        policy.reset("repeated-zero")
        policy.observe(solid_rgba(255, 0, 0))
        policy.act(instruction="Continue.", decision_step=0)

        with self.assertRaisesRegex(
            ValueError,
            r"decision_step.*expected 1.*got 0",
        ):
            policy.act(instruction="Continue.", decision_step=0)

        self.assertEqual(len(runtime.calls), 1)

    def test_act_rejects_skipped_or_out_of_order_decision_steps(self) -> None:
        runtime = FakeRuntime(["forward 25 cm", "stop"])
        policy = OfficialNaVIDAPolicy(runtime=runtime)
        policy.reset("strict-sequencing")
        policy.observe(solid_rgba(255, 0, 0))

        with self.assertRaisesRegex(
            ValueError,
            r"decision_step.*expected 0.*got 1",
        ):
            policy.act(instruction="Continue.", decision_step=1)

        policy.act(instruction="Continue.", decision_step=0)
        policy.observe(solid_rgba(0, 255, 0))

        with self.assertRaisesRegex(
            ValueError,
            r"decision_step.*expected 1.*got 2",
        ):
            policy.act(instruction="Continue.", decision_step=2)

        self.assertEqual(len(runtime.calls), 1)

    def test_act_rejects_empty_or_non_string_instruction(self) -> None:
        policy = OfficialNaVIDAPolicy(runtime=FakeRuntime(["stop"]))
        policy.reset("invalid-instruction")
        policy.observe(solid_rgba(255, 0, 0))

        for instruction in ("", "   ", None):
            with self.subTest(instruction=instruction):
                with self.assertRaisesRegex(ValueError, "instruction"):
                    policy.act(  # type: ignore[arg-type]
                        instruction=instruction,
                        decision_step=0,
                    )

    def test_act_accepts_valid_sequential_decisions(self) -> None:
        runtime = FakeRuntime(
            ["forward 25 cm", "turn left 15 degree", "stop"]
        )
        policy = OfficialNaVIDAPolicy(runtime=runtime)
        policy.reset("sequential")

        decisions = []
        for decision_step in range(3):
            policy.observe(solid_rgba(decision_step, 0, 0))
            decisions.append(
                policy.act(
                    instruction="Continue.",
                    decision_step=decision_step,
                )
            )

        self.assertEqual(
            [decision.decision_step for decision in decisions],
            [0, 1, 2],
        )
        self.assertEqual(len(runtime.calls), 3)

    def test_decision_to_dict_is_json_serializable(self) -> None:
        policy = OfficialNaVIDAPolicy(
            runtime=FakeRuntime(["forward 25 cm, turn left 15 degree"])
        )
        policy.reset("serialization")
        policy.observe(solid_rgba(255, 0, 0))
        decision = policy.act(instruction="Navigate.", decision_step=0)

        serialized = decision.to_dict()

        json.dumps(serialized)
        self.assertEqual(serialized["protocol"], "paper_pure")
        self.assertEqual(
            serialized["parsed_sub_chunks"],
            [
                {"kind": "forward", "amount": 25},
                {"kind": "turn_left", "amount": 15},
            ],
        )
        self.assertEqual(
            serialized["atomic_actions"],
            ["move_forward", "turn_left"],
        )
        self.assertEqual(
            serialized["metadata"],
            {
                "stored_frame_count": 1,
                "available_history_count": 0,
                "sampled_history_count": 0,
                "input_token_count": 101,
                "generated_token_count": 7,
                "latency_seconds": 0.25,
                "peak_allocated_gib": 1.5,
                "peak_reserved_gib": 2.0,
                "parsed_sub_chunks": [
                    {"kind": "forward", "amount": 25},
                    {"kind": "turn_left", "amount": 15},
                ],
                "parsed_sub_chunk_count": 2,
                "max_executed_sub_chunks": 2,
                "executed_sub_chunk_count": 2,
                "ignored_sub_chunk_count": 0,
                "atomic_actions": [
                    "move_forward",
                    "turn_left",
                ],
                "atomic_action_count": 2,
            },
        )

    def test_close_is_idempotent_and_runtime_is_reused_across_resets(
        self,
    ) -> None:
        runtime = ClosableFakeRuntime(["stop", "stop"])
        policy = OfficialNaVIDAPolicy(runtime=runtime)

        for episode_id in ("episode-1", "episode-2"):
            policy.reset(episode_id)
            policy.observe(solid_rgba(255, 0, 0))
            policy.act(instruction="Stop.", decision_step=0)

        self.assertEqual(len(runtime.calls), 2)
        self.assertEqual(runtime.close_calls, 0)

        policy.close()
        policy.close()

        self.assertEqual(runtime.close_calls, 1)
        self.assertIsNone(policy._expected_decision_step)
        with self.assertRaisesRegex(RuntimeError, "closed"):
            policy.reset("episode-3")

    def test_close_accepts_runtime_without_close_method(self) -> None:
        policy = OfficialNaVIDAPolicy(runtime=FakeRuntime(["stop"]))
        policy.reset("no-runtime-close")
        policy.observe(solid_rgba(255, 0, 0))

        policy.close()
        policy.close()

    def test_reset_clears_the_previous_current_observation(self) -> None:
        policy = OfficialNaVIDAPolicy(runtime=FakeRuntime(["stop"]))
        policy.reset("episode-1")
        policy.observe(solid_rgba(255, 0, 0))

        policy.reset("episode-2")

        with self.assertRaisesRegex(RuntimeError, r"observe\(rgb\)"):
            policy.act(instruction="Stop.", decision_step=0)


if __name__ == "__main__":
    unittest.main()

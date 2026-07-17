import json
import tempfile
import unittest
from pathlib import Path

from navida_habitat.action_chunk import HabitatAction
from navida_habitat.episode_log import EpisodeStepLog, EpisodeSummary, write_jsonl
from navida_habitat.episode_runner import EpisodeRunner
from navida_habitat.mock_backend import BackendExhaustedError, MockBackend
from navida_habitat.mock_env import MockEnv


class MockBackendTests(unittest.TestCase):
    def test_returns_configured_outputs_then_fails_explicitly(self) -> None:
        backend = MockBackend(["forward 25 cm", "stop"])

        self.assertEqual(
            backend.infer(instruction="walk ahead", step=0),
            "forward 25 cm",
        )
        self.assertEqual(backend.infer(instruction="walk ahead", step=1), "stop")
        with self.assertRaisesRegex(BackendExhaustedError, "exhausted"):
            backend.infer(instruction="walk ahead", step=2)

        self.assertEqual(backend.call_count, 3)


class MockEnvTests(unittest.TestCase):
    def test_updates_position_from_current_yaw_and_normalizes_turns(self) -> None:
        environment = MockEnv()

        environment.execute(HabitatAction.MOVE_FORWARD)
        environment.execute(HabitatAction.TURN_LEFT)
        environment.execute(HabitatAction.TURN_LEFT)
        environment.execute(HabitatAction.MOVE_FORWARD)

        self.assertAlmostEqual(environment.position_x, -0.125)
        self.assertAlmostEqual(environment.position_z, 0.4665063509461097)
        self.assertEqual(environment.yaw_degrees, 30.0)
        self.assertEqual(
            environment.executed_actions,
            [
                HabitatAction.MOVE_FORWARD,
                HabitatAction.TURN_LEFT,
                HabitatAction.TURN_LEFT,
                HabitatAction.MOVE_FORWARD,
            ],
        )

        for _ in range(14):
            environment.execute(HabitatAction.TURN_RIGHT)

        self.assertEqual(environment.yaw_degrees, -180.0)


class EpisodeLogTests(unittest.TestCase):
    def test_writes_one_valid_json_object_per_step_with_required_fields(self) -> None:
        step_log = EpisodeStepLog(
            episode_id="episode-1",
            step=0,
            instruction="walk ahead",
            raw_model_output="forward 50 cm",
            parsed_sub_chunks=[{"kind": "forward", "amount": 50}],
            atomic_actions=["move_forward", "move_forward"],
            executed_actions=["move_forward", "move_forward"],
            position={"x": 0.0, "z": 0.5},
            yaw_degrees=0.0,
            done=False,
            success=False,
            termination_reason=None,
            error=None,
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "nested" / "episode.jsonl"
            write_jsonl(log_path, [step_log])
            lines = log_path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(lines), 1)
        decoded = json.loads(lines[0])
        self.assertEqual(decoded, step_log.to_dict())
        self.assertEqual(
            set(decoded),
            {
                "episode_id",
                "step",
                "instruction",
                "raw_model_output",
                "parsed_sub_chunks",
                "atomic_actions",
                "executed_actions",
                "position",
                "yaw_degrees",
                "done",
                "success",
                "termination_reason",
                "error",
            },
        )

        summary = EpisodeSummary(
            episode_id="episode-1",
            steps=1,
            done=False,
            success=False,
            termination_reason="max_steps",
            error=None,
        )
        self.assertEqual(summary.to_dict()["termination_reason"], "max_steps")


class EpisodeRunnerTests(unittest.TestCase):
    def test_executes_multiple_sub_chunks_from_one_model_decision(self) -> None:
        environment = MockEnv()
        summary = EpisodeRunner(
            backend=MockBackend(["forward 25 cm, stop"]),
            environment=environment,
            max_steps=3,
        ).run(
            episode_id="multi-sub-chunk-episode",
            instruction="walk ahead and stop",
        )

        self.assertEqual(summary.termination_reason, "stop")
        self.assertEqual(summary.steps, 1)
        self.assertEqual(
            environment.executed_actions,
            [HabitatAction.MOVE_FORWARD, HabitatAction.STOP],
        )

    def test_runs_expanded_actions_and_terminates_successfully_on_stop(self) -> None:
        backend = MockBackend(
            ["forward 50 cm", "turn left 30 degree", "stop"]
        )
        environment = MockEnv()

        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "episode.jsonl"
            runner = EpisodeRunner(
                backend=backend,
                environment=environment,
                max_steps=5,
                log_path=log_path,
            )
            summary = runner.run(
                episode_id="normal-episode",
                instruction="walk forward and turn left",
            )
            decoded_logs = [
                json.loads(line)
                for line in log_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(summary.termination_reason, "stop")
        self.assertEqual(summary.steps, 3)
        self.assertTrue(summary.done)
        self.assertTrue(summary.success)
        self.assertIsNone(summary.error)
        self.assertEqual(backend.call_count, 3)
        self.assertEqual(
            environment.executed_actions,
            [
                HabitatAction.MOVE_FORWARD,
                HabitatAction.MOVE_FORWARD,
                HabitatAction.TURN_LEFT,
                HabitatAction.TURN_LEFT,
                HabitatAction.STOP,
            ],
        )
        self.assertAlmostEqual(environment.position_x, 0.0)
        self.assertAlmostEqual(environment.position_z, 0.5)
        self.assertEqual(environment.yaw_degrees, 30.0)
        self.assertEqual(len(decoded_logs), 3)
        self.assertEqual(decoded_logs[0]["raw_model_output"], "forward 50 cm")
        self.assertEqual(
            decoded_logs[0]["parsed_sub_chunks"],
            [{"kind": "forward", "amount": 50}],
        )
        self.assertEqual(
            decoded_logs[0]["atomic_actions"],
            ["move_forward", "move_forward"],
        )
        self.assertEqual(
            decoded_logs[0]["executed_actions"],
            ["move_forward", "move_forward"],
        )
        self.assertEqual(
            decoded_logs[1]["atomic_actions"],
            ["turn_left", "turn_left"],
        )
        self.assertEqual(decoded_logs[2]["termination_reason"], "stop")

    def test_invalid_output_fails_without_executing_fallback_actions(self) -> None:
        backend = MockBackend(["forward 25 cm because it is clear", "stop"])
        environment = MockEnv()

        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "invalid.jsonl"
            summary = EpisodeRunner(
                backend=backend,
                environment=environment,
                max_steps=5,
                log_path=log_path,
            ).run(
                episode_id="invalid-episode",
                instruction="walk ahead",
            )
            log_entry = json.loads(log_path.read_text(encoding="utf-8"))

        self.assertEqual(summary.termination_reason, "invalid_output")
        self.assertEqual(summary.steps, 1)
        self.assertFalse(summary.done)
        self.assertFalse(summary.success)
        self.assertIsNotNone(summary.error)
        self.assertEqual(backend.call_count, 1)
        self.assertEqual(environment.executed_actions, [])
        self.assertEqual(
            log_entry["raw_model_output"],
            "forward 25 cm because it is clear",
        )
        self.assertEqual(log_entry["parsed_sub_chunks"], [])
        self.assertEqual(log_entry["atomic_actions"], [])
        self.assertEqual(log_entry["executed_actions"], [])
        self.assertEqual(log_entry["termination_reason"], "invalid_output")
        self.assertIsNotNone(log_entry["error"])

    def test_missing_stop_terminates_at_model_decision_step_limit(self) -> None:
        backend = MockBackend(
            ["forward 50 cm", "forward 50 cm", "stop"]
        )
        environment = MockEnv()

        runner = EpisodeRunner(
            backend=backend,
            environment=environment,
            max_steps=2,
        )
        summary = runner.run(
            episode_id="bounded-episode",
            instruction="keep walking",
        )

        self.assertEqual(summary.termination_reason, "max_steps")
        self.assertEqual(summary.steps, 2)
        self.assertFalse(summary.done)
        self.assertFalse(summary.success)
        self.assertIsNone(summary.error)
        self.assertEqual(backend.call_count, 2)
        self.assertEqual(
            environment.executed_actions,
            [HabitatAction.MOVE_FORWARD] * 4,
        )
        self.assertEqual(runner.step_logs[-1].termination_reason, "max_steps")

    def test_backend_exhaustion_is_an_explicit_failure(self) -> None:
        backend = MockBackend(["forward 25 cm"])
        environment = MockEnv()

        runner = EpisodeRunner(
            backend=backend,
            environment=environment,
            max_steps=3,
        )
        summary = runner.run(
            episode_id="exhausted-episode",
            instruction="walk until told to stop",
        )

        self.assertEqual(summary.termination_reason, "backend_exhausted")
        self.assertEqual(summary.steps, 2)
        self.assertFalse(summary.done)
        self.assertFalse(summary.success)
        self.assertIn("exhausted", summary.error or "")
        self.assertEqual(backend.call_count, 2)
        self.assertEqual(
            environment.executed_actions,
            [HabitatAction.MOVE_FORWARD],
        )
        failed_step = runner.step_logs[-1]
        self.assertEqual(failed_step.step, 1)
        self.assertIsNone(failed_step.raw_model_output)
        self.assertEqual(failed_step.parsed_sub_chunks, [])
        self.assertEqual(failed_step.atomic_actions, [])
        self.assertEqual(failed_step.executed_actions, [])
        self.assertEqual(failed_step.termination_reason, "backend_exhausted")

    def test_unexpected_backend_exception_is_a_runtime_error(self) -> None:
        class FailingBackend(MockBackend):
            def infer(self, *, instruction: str, step: int) -> str:
                del instruction, step
                raise RuntimeError("backend failed")

        runner = EpisodeRunner(
            backend=FailingBackend([]),
            environment=MockEnv(),
            max_steps=3,
        )

        summary = runner.run(
            episode_id="runtime-error-episode",
            instruction="walk ahead",
        )

        self.assertEqual(summary.termination_reason, "runtime_error")
        self.assertEqual(summary.steps, 1)
        self.assertFalse(summary.done)
        self.assertFalse(summary.success)
        self.assertIn("RuntimeError: backend failed", summary.error or "")
        self.assertEqual(runner.step_logs[0].termination_reason, "runtime_error")
        self.assertEqual(runner.step_logs[0].error, summary.error)

    def test_environment_exception_preserves_decision_trace(self) -> None:
        class FailingEnv(MockEnv):
            def execute(self, action: HabitatAction) -> None:
                del action
                raise RuntimeError("environment failed")

        environment = FailingEnv()
        runner = EpisodeRunner(
            backend=MockBackend(["forward 25 cm"]),
            environment=environment,
            max_steps=3,
        )

        summary = runner.run(
            episode_id="environment-error-episode",
            instruction="walk ahead",
        )

        self.assertEqual(summary.termination_reason, "runtime_error")
        self.assertIn("RuntimeError: environment failed", summary.error or "")
        self.assertEqual(environment.executed_actions, [])
        failed_step = runner.step_logs[0]
        self.assertEqual(failed_step.raw_model_output, "forward 25 cm")
        self.assertEqual(
            failed_step.parsed_sub_chunks,
            [{"kind": "forward", "amount": 25}],
        )
        self.assertEqual(failed_step.atomic_actions, ["move_forward"])
        self.assertEqual(failed_step.executed_actions, [])


if __name__ == "__main__":
    unittest.main()

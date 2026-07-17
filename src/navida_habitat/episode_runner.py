"""Bounded pure-Python episode loop for deterministic mock execution."""

from __future__ import annotations

from pathlib import Path

from navida_habitat.action_chunk import (
    ActionParseError,
    expand_action_chunk,
    parse_action_chunk,
)
from navida_habitat.episode_log import EpisodeStepLog, EpisodeSummary, write_jsonl
from navida_habitat.mock_backend import BackendExhaustedError, MockBackend
from navida_habitat.mock_env import MockEnv


class EpisodeRunner:
    """Connect raw backend text to parsing, expansion, execution, and logs."""

    def __init__(
        self,
        *,
        backend: MockBackend,
        environment: MockEnv,
        max_steps: int,
        log_path: str | Path | None = None,
    ) -> None:
        if max_steps <= 0:
            raise ValueError("max_steps must be positive")
        self.backend = backend
        self.environment = environment
        self.max_steps = max_steps
        self.log_path = Path(log_path) if log_path is not None else None
        self.step_logs: list[EpisodeStepLog] = []

    def run(self, *, episode_id: str, instruction: str) -> EpisodeSummary:
        """Run one episode until stop or the model-decision step limit."""

        self.step_logs = []
        for step in range(self.max_steps):
            try:
                raw_model_output = self.backend.infer(
                    instruction=instruction,
                    step=step,
                )
            except BackendExhaustedError as error:
                return self._terminate_with_error(
                    episode_id=episode_id,
                    step=step,
                    instruction=instruction,
                    raw_model_output=None,
                    parsed_sub_chunks=[],
                    atomic_actions=[],
                    executed_actions=[],
                    termination_reason="backend_exhausted",
                    error_message=str(error),
                )
            except Exception as error:
                return self._terminate_with_error(
                    episode_id=episode_id,
                    step=step,
                    instruction=instruction,
                    raw_model_output=None,
                    parsed_sub_chunks=[],
                    atomic_actions=[],
                    executed_actions=[],
                    termination_reason="runtime_error",
                    error_message=self._format_runtime_error(error),
                )

            try:
                action_chunk = parse_action_chunk(raw_model_output)
            except ActionParseError as error:
                return self._terminate_with_error(
                    episode_id=episode_id,
                    step=step,
                    instruction=instruction,
                    raw_model_output=raw_model_output,
                    parsed_sub_chunks=[],
                    atomic_actions=[],
                    executed_actions=[],
                    termination_reason="invalid_output",
                    error_message=str(error),
                )
            except Exception as error:
                return self._terminate_with_error(
                    episode_id=episode_id,
                    step=step,
                    instruction=instruction,
                    raw_model_output=raw_model_output,
                    parsed_sub_chunks=[],
                    atomic_actions=[],
                    executed_actions=[],
                    termination_reason="runtime_error",
                    error_message=self._format_runtime_error(error),
                )

            parsed_sub_chunks = [
                {
                    "kind": sub_chunk.kind.value,
                    "amount": sub_chunk.amount,
                }
                for sub_chunk in action_chunk.sub_chunks
            ]
            first_action_index = len(self.environment.executed_actions)
            atomic_actions = ()
            try:
                atomic_actions = expand_action_chunk(action_chunk)
                for action in atomic_actions:
                    self.environment.execute(action)
            except Exception as error:
                executed_actions = self.environment.executed_actions[
                    first_action_index:
                ]
                return self._terminate_with_error(
                    episode_id=episode_id,
                    step=step,
                    instruction=instruction,
                    raw_model_output=raw_model_output,
                    parsed_sub_chunks=parsed_sub_chunks,
                    atomic_actions=[action.value for action in atomic_actions],
                    executed_actions=[
                        action.value for action in executed_actions
                    ],
                    termination_reason="runtime_error",
                    error_message=self._format_runtime_error(error),
                )

            executed_actions = self.environment.executed_actions[
                first_action_index:
            ]
            termination_reason = None
            if self.environment.done:
                termination_reason = "stop"
            elif step + 1 == self.max_steps:
                termination_reason = "max_steps"

            self._append_step_log(
                episode_id=episode_id,
                step=step,
                instruction=instruction,
                raw_model_output=raw_model_output,
                parsed_sub_chunks=parsed_sub_chunks,
                atomic_actions=[action.value for action in atomic_actions],
                executed_actions=[action.value for action in executed_actions],
                termination_reason=termination_reason,
                error=None,
            )

            if termination_reason is not None:
                return self._finish(
                    episode_id=episode_id,
                    termination_reason=termination_reason,
                    error=None,
                )

        raise AssertionError("positive max_steps must terminate the episode loop")

    def _terminate_with_error(
        self,
        *,
        episode_id: str,
        step: int,
        instruction: str,
        raw_model_output: str | None,
        parsed_sub_chunks: list[dict[str, object]],
        atomic_actions: list[str],
        executed_actions: list[str],
        termination_reason: str,
        error_message: str,
    ) -> EpisodeSummary:
        self._append_step_log(
            episode_id=episode_id,
            step=step,
            instruction=instruction,
            raw_model_output=raw_model_output,
            parsed_sub_chunks=parsed_sub_chunks,
            atomic_actions=atomic_actions,
            executed_actions=executed_actions,
            termination_reason=termination_reason,
            error=error_message,
        )
        return self._finish(
            episode_id=episode_id,
            termination_reason=termination_reason,
            error=error_message,
        )

    def _append_step_log(
        self,
        *,
        episode_id: str,
        step: int,
        instruction: str,
        raw_model_output: str | None,
        parsed_sub_chunks: list[dict[str, object]],
        atomic_actions: list[str],
        executed_actions: list[str],
        termination_reason: str | None,
        error: str | None,
    ) -> None:
        self.step_logs.append(
            EpisodeStepLog(
                episode_id=episode_id,
                step=step,
                instruction=instruction,
                raw_model_output=raw_model_output,
                parsed_sub_chunks=parsed_sub_chunks,
                atomic_actions=atomic_actions,
                executed_actions=executed_actions,
                position={
                    "x": self.environment.position_x,
                    "z": self.environment.position_z,
                },
                yaw_degrees=self.environment.yaw_degrees,
                done=self.environment.done,
                success=self.environment.success,
                termination_reason=termination_reason,
                error=error,
            )
        )

    @staticmethod
    def _format_runtime_error(error: Exception) -> str:
        return f"{type(error).__name__}: {error}"

    def _finish(
        self,
        *,
        episode_id: str,
        termination_reason: str,
        error: str | None,
    ) -> EpisodeSummary:
        if self.log_path is not None:
            write_jsonl(self.log_path, self.step_logs)
        return EpisodeSummary(
            episode_id=episode_id,
            steps=len(self.step_logs),
            done=self.environment.done,
            success=self.environment.success,
            termination_reason=termination_reason,
            error=error,
        )

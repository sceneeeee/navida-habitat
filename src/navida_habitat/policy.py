"""Evaluator-facing Official NaVIDA policy API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from navida_habitat.action_chunk import (
    ActionParseError,
    ActionSubChunk,
    DEFAULT_MAX_SUB_CHUNKS,
    HabitatAction,
    expand_action_chunk,
    parse_action_chunk,
)
from navida_habitat.navida_backend import (
    NaVIDABackend,
    NaVIDARuntimeProtocol,
)


@dataclass(frozen=True, slots=True)
class NaVIDAPolicyDecision:
    """One parsed NaVIDA decision returned to an external evaluator."""

    episode_id: str
    decision_step: int
    protocol: str
    raw_output: str
    parsed_sub_chunks: tuple[ActionSubChunk, ...]
    atomic_actions: tuple[HabitatAction, ...]
    valid: bool
    error: str | None
    latency_seconds: float
    metadata: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        """Return a fully JSON-serializable decision representation."""

        return {
            "episode_id": self.episode_id,
            "decision_step": self.decision_step,
            "protocol": self.protocol,
            "raw_output": self.raw_output,
            "parsed_sub_chunks": [
                {
                    "kind": sub_chunk.kind.value,
                    "amount": sub_chunk.amount,
                }
                for sub_chunk in self.parsed_sub_chunks
            ],
            "atomic_actions": [
                action.value
                for action in self.atomic_actions
            ],
            "valid": self.valid,
            "error": self.error,
            "latency_seconds": self.latency_seconds,
            "metadata": dict(self.metadata),
        }


class _PolicyObservationProvider:
    """Hold the evaluator's most recently supplied RGB observation."""

    def __init__(self) -> None:
        self.rgb_observation: Any | None = None


class OfficialNaVIDAPolicy:
    """Expose paper-pure NaVIDA decisions without owning an environment."""

    def __init__(
        self,
        *,
        runtime: NaVIDARuntimeProtocol,
        protocol: str = "paper_pure",
    ) -> None:
        if protocol != "paper_pure":
            raise NotImplementedError(
                "OfficialNaVIDAPolicy currently supports only "
                "protocol='paper_pure'"
            )

        self.runtime = runtime
        self.protocol = protocol
        self._observation_provider = _PolicyObservationProvider()
        self._backend = NaVIDABackend(
            runtime=runtime,
            observation_provider=self._observation_provider,
        )
        self._episode_id: str | None = None
        self._expected_decision_step: int | None = None
        self._closed = False

    def reset(self, episode_id: str) -> None:
        """Clear episode state and begin a new evaluator episode."""

        self._require_open()
        if not isinstance(episode_id, str) or not episode_id.strip():
            raise ValueError("episode_id must be a non-empty string")

        self._backend.reset()
        self._observation_provider.rgb_observation = None
        self._episode_id = episode_id
        self._expected_decision_step = 0

    def observe(self, rgb: Any) -> None:
        """Capture the evaluator's latest RGB observation."""

        self._require_open()
        if self._episode_id is None:
            raise RuntimeError(
                "policy.reset(episode_id) must be called before observe(rgb)"
            )

        previous_observation = self._observation_provider.rgb_observation
        self._observation_provider.rgb_observation = rgb
        try:
            self._backend.observe()
        except Exception:
            self._observation_provider.rgb_observation = previous_observation
            raise

        self._observation_provider.rgb_observation = (
            self._backend.frame_history.latest
        )

    def act(
        self,
        *,
        instruction: str,
        decision_step: int,
    ) -> NaVIDAPolicyDecision:
        """Generate actions for the evaluator without executing them."""

        self._require_open()
        if self._episode_id is None:
            raise RuntimeError("policy.reset(episode_id) must be called before act")
        if self._observation_provider.rgb_observation is None:
            raise RuntimeError("policy.observe(rgb) must be called before act")
        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError("instruction must be a non-empty string")
        if decision_step != self._expected_decision_step:
            raise ValueError(
                "decision_step out of sequence: "
                f"expected {self._expected_decision_step}, got {decision_step}"
            )

        raw_output = self._backend.infer(
            instruction=instruction,
            step=decision_step,
        )
        self._expected_decision_step += 1
        record = self._backend.decision_records[-1]

        metadata = record.to_dict()
        del metadata["step"]
        del metadata["raw_output"]

        try:
            action_chunk = parse_action_chunk(raw_output)
        except ActionParseError as error:
            parsed_sub_chunks: tuple[ActionSubChunk, ...] = ()
            atomic_actions: tuple[HabitatAction, ...] = ()
            valid = False
            error_message: str | None = str(error)
        else:
            parsed_sub_chunks = action_chunk.sub_chunks
            atomic_actions = expand_action_chunk(action_chunk)
            valid = True
            error_message = None

        executed_sub_chunk_count = min(
            len(parsed_sub_chunks),
            DEFAULT_MAX_SUB_CHUNKS,
        )
        metadata.update(
            {
                "parsed_sub_chunks": [
                    {
                        "kind": sub_chunk.kind.value,
                        "amount": sub_chunk.amount,
                    }
                    for sub_chunk in parsed_sub_chunks
                ],
                "parsed_sub_chunk_count": len(parsed_sub_chunks),
                "max_executed_sub_chunks": DEFAULT_MAX_SUB_CHUNKS,
                "executed_sub_chunk_count": executed_sub_chunk_count,
                "ignored_sub_chunk_count": (
                    len(parsed_sub_chunks) - executed_sub_chunk_count
                ),
                "atomic_actions": [
                    action.value
                    for action in atomic_actions
                ],
                "atomic_action_count": len(atomic_actions),
            }
        )

        return NaVIDAPolicyDecision(
            episode_id=self._episode_id,
            decision_step=decision_step,
            protocol=self.protocol,
            raw_output=raw_output,
            parsed_sub_chunks=parsed_sub_chunks,
            atomic_actions=atomic_actions,
            valid=valid,
            error=error_message,
            latency_seconds=record.result.latency_seconds,
            metadata=metadata,
        )

    def close(self) -> None:
        """Release runtime resources once and clear all episode state."""

        if self._closed:
            return

        self._closed = True
        self._backend.reset()
        self._observation_provider.rgb_observation = None
        self._episode_id = None
        self._expected_decision_step = None

        close_runtime = getattr(self.runtime, "close", None)
        if callable(close_runtime):
            close_runtime()

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("policy is closed")

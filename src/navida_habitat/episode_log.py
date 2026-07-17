"""Serializable episode logs for the pure-Python mock loop."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class EpisodeStepLog:
    """Trace one attempted model decision step."""

    episode_id: str
    step: int
    instruction: str
    raw_model_output: str | None
    parsed_sub_chunks: list[dict[str, object]]
    atomic_actions: list[str]
    executed_actions: list[str]
    position: dict[str, float]
    yaw_degrees: float
    done: bool
    success: bool
    termination_reason: str | None
    error: str | None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return asdict(self)


@dataclass(frozen=True, slots=True)
class EpisodeSummary:
    """Final outcome of one episode."""

    episode_id: str
    steps: int
    done: bool
    success: bool
    termination_reason: str
    error: str | None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return asdict(self)


def write_jsonl(
    path: str | Path, step_logs: Iterable[EpisodeStepLog]
) -> None:
    """Write step logs as one JSON object per line, creating parents."""

    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log_file:
        for step_log in step_logs:
            log_file.write(json.dumps(step_log.to_dict(), ensure_ascii=False))
            log_file.write("\n")

"""Run a deterministic Stage 1 mock episode."""

from __future__ import annotations

import json
from pathlib import Path

from navida_habitat.episode_runner import EpisodeRunner
from navida_habitat.mock_backend import MockBackend
from navida_habitat.mock_env import MockEnv


def main() -> None:
    backend = MockBackend(
        ["forward 50 cm", "turn left 30 degree", "stop"]
    )
    environment = MockEnv()
    runner = EpisodeRunner(
        backend=backend,
        environment=environment,
        max_steps=5,
        log_path=Path("logs/mock/mock_episode.jsonl"),
    )

    summary = runner.run(
        episode_id="mock_episode",
        instruction="Walk forward, turn left, then stop.",
    )
    print(json.dumps(summary.to_dict(), ensure_ascii=False))


if __name__ == "__main__":
    main()

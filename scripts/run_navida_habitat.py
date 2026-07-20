"""Run the official NaVIDA checkpoint in a Habitat-Sim scene."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from navida_habitat.episode_runner import EpisodeRunner
from navida_habitat.habitat_env import HabitatEnvAdapter
from navida_habitat.model_runtime import (
    NaVIDAGenerationSettings,
    NaVIDAModelRuntime,
)
from navida_habitat.navida_backend import (
    NaVIDABackend,
    observation_to_rgb_image,
)


def positive_int(value: str) -> int:
    """Parse a strictly positive integer."""

    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError(
            f"expected a positive integer, got {value!r}"
        )
    return parsed


def parse_args(
    argv: Sequence[str] | None = None,
) -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene-path", required=True, type=Path)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--instruction", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--episode-id",
        default="navida-habitat-episode",
    )
    parser.add_argument(
        "--max-steps",
        default=2,
        type=positive_int,
    )
    parser.add_argument(
        "--max-new-tokens",
        default=128,
        type=positive_int,
    )
    parser.add_argument(
        "--max-action-history",
        default=200,
        type=positive_int,
    )
    parser.add_argument(
        "--history-sample-count",
        default=8,
        type=positive_int,
    )

    args = parser.parse_args(argv)

    if args.history_sample_count < 2:
        parser.error("--history-sample-count must be at least 2")

    return args


def write_json(
    path: Path,
    payload: dict[str, object],
) -> None:
    """Write formatted UTF-8 JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def run(
    args: argparse.Namespace,
    *,
    environment_factory: Any = HabitatEnvAdapter,
    runtime_factory: Any = NaVIDAModelRuntime,
) -> dict[str, object]:
    """Run one bounded NaVIDA-Habitat episode."""

    scene_path = args.scene_path.expanduser().resolve()
    model_path = args.model_path.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()

    if not scene_path.is_file():
        raise FileNotFoundError(
            f"Habitat scene does not exist: {scene_path}"
        )

    if not model_path.is_dir():
        raise FileNotFoundError(
            f"NaVIDA model directory does not exist: {model_path}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    log_path = output_dir / "episode.jsonl"
    summary_path = output_dir / "summary.json"
    initial_rgb_path = output_dir / "initial_rgb.png"
    final_rgb_path = output_dir / "final_rgb.png"

    environment = environment_factory(
        scene_path=scene_path,
    )

    with environment:
        initial_position = dict(environment.position)
        initial_yaw = float(environment.rotation_yaw)

        observation_to_rgb_image(
            environment.rgb_observation
        ).save(initial_rgb_path)

        runtime = runtime_factory(
            model_path,
            settings=NaVIDAGenerationSettings(
                max_new_tokens=args.max_new_tokens,
            ),
        )

        backend = NaVIDABackend(
            runtime=runtime,
            observation_provider=environment,
            max_action_history=args.max_action_history,
            history_sample_count=args.history_sample_count,
        )

        runner = EpisodeRunner(
            backend=backend,
            environment=environment,
            max_steps=args.max_steps,
            log_path=log_path,
        )

        runtime.load()

        summary = runner.run(
            episode_id=args.episode_id,
            instruction=args.instruction,
        )

        final_position = dict(environment.position)
        final_yaw = float(environment.rotation_yaw)

        observation_to_rgb_image(
            environment.rgb_observation
        ).save(final_rgb_path)

        payload: dict[str, object] = {
            "episode": summary.to_dict(),
            "configuration": {
                "scene_path": str(scene_path),
                "model_path": str(model_path),
                "instruction": args.instruction,
                "episode_id": args.episode_id,
                "max_steps": args.max_steps,
                "max_new_tokens": args.max_new_tokens,
                "max_action_history": args.max_action_history,
                "history_sample_count": args.history_sample_count,
                "execution_policy": (
                    "strict_parser_first_two_chunks"
                ),
            },
            "initial_state": {
                "position": initial_position,
                "yaw_degrees": initial_yaw,
            },
            "final_state": {
                "position": final_position,
                "yaw_degrees": final_yaw,
            },
            "decisions": [
                record.to_dict()
                for record in backend.decision_records
            ],
            "final_stored_frame_count": len(
                backend.frame_history
            ),
            "artifacts": {
                "episode_jsonl": str(log_path),
                "summary_json": str(summary_path),
                "initial_rgb": str(initial_rgb_path),
                "final_rgb": str(final_rgb_path),
            },
        }

    payload["simulator_closed"] = environment.closed
    write_json(summary_path, payload)

    return payload


def main() -> None:
    """Run the command-line application."""

    payload = run(parse_args())
    print(
        json.dumps(
            payload,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

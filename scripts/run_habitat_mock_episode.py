"""Run a deterministic mock backend through a real Habitat-Sim scene."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from navida_habitat.episode_runner import EpisodeRunner
from navida_habitat.habitat_env import HabitatEnvAdapter
from navida_habitat.mock_backend import MockBackend


def parse_args() -> argparse.Namespace:
    """Parse the Stage 2 real-scene execution arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--episode-id", default="stage2-habitat-demo")
    parser.add_argument(
        "--instruction",
        default="Walk forward and turn left.",
    )
    parser.add_argument("--max-steps", default=10, type=int)
    return parser.parse_args()


def _rgb_metadata(observation: Any) -> dict[str, object]:
    shape = getattr(observation, "shape", ())
    return {
        "rgb_shape": [int(dimension) for dimension in shape],
        "rgb_dtype": str(getattr(observation, "dtype", "unknown")),
    }


def main() -> None:
    args = parse_args()
    backend = MockBackend(
        ["forward 50 cm, turn left 30 degree", "stop"]
    )
    environment = HabitatEnvAdapter(scene_path=args.scene)

    with environment:
        initial_position = dict(environment.position)
        initial_rotation_yaw = environment.rotation_yaw
        runner = EpisodeRunner(
            backend=backend,
            environment=environment,
            max_steps=args.max_steps,
            log_path=args.output,
        )
        summary = runner.run(
            episode_id=args.episode_id,
            instruction=args.instruction,
        )
        final_position = dict(environment.position)
        final_rotation_yaw = environment.rotation_yaw
        rgb_metadata = _rgb_metadata(environment.rgb_observation)

    output = {
        **summary.to_dict(),
        "termination": summary.termination_reason,
        "output": str(args.output),
        "initial_position": initial_position,
        "final_position": final_position,
        "initial_rotation_yaw": initial_rotation_yaw,
        "final_rotation_yaw": final_rotation_yaw,
        "simulator_closed": environment.closed,
        **rgb_metadata,
    }
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()

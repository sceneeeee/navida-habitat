"""Habitat-Sim environment adapter with lazy external imports."""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

from navida_habitat.action_chunk import HabitatAction


SimulatorFactory = Callable[[str], Any]


def _create_habitat_simulator(scene_path: str) -> Any:
    import habitat_sim  # type: ignore[import-not-found]

    simulator_configuration = habitat_sim.SimulatorConfiguration()
    simulator_configuration.scene_id = scene_path

    rgb_sensor = habitat_sim.CameraSensorSpec()
    rgb_sensor.uuid = "rgb"
    rgb_sensor.sensor_type = habitat_sim.SensorType.COLOR
    rgb_sensor.sensor_subtype = habitat_sim.SensorSubType.PINHOLE
    rgb_sensor.resolution = [128, 128]
    rgb_sensor.position = [0.0, 1.5, 0.0]

    agent_configuration = habitat_sim.agent.AgentConfiguration()
    agent_configuration.sensor_specifications = [rgb_sensor]
    agent_configuration.action_space = {
        "move_forward": habitat_sim.agent.ActionSpec(
            "move_forward",
            habitat_sim.agent.ActuationSpec(amount=0.25),
        ),
        "turn_left": habitat_sim.agent.ActionSpec(
            "turn_left",
            habitat_sim.agent.ActuationSpec(amount=15.0),
        ),
        "turn_right": habitat_sim.agent.ActionSpec(
            "turn_right",
            habitat_sim.agent.ActuationSpec(amount=15.0),
        ),
    }

    configuration = habitat_sim.Configuration(
        simulator_configuration,
        [agent_configuration],
    )
    return habitat_sim.Simulator(configuration)


class HabitatEnvAdapter:
    """Adapt Habitat-Sim to the atomic episode environment interface."""

    _ACTION_MAPPING = {
        HabitatAction.MOVE_FORWARD: "move_forward",
        HabitatAction.TURN_LEFT: "turn_left",
        HabitatAction.TURN_RIGHT: "turn_right",
    }

    def __init__(
        self,
        scene_path: str | Path,
        *,
        simulator_factory: SimulatorFactory | None = None,
    ) -> None:
        self.scene_path = Path(scene_path)
        factory = simulator_factory or _create_habitat_simulator
        self._simulator: Any | None = None
        self._closed = False
        self._done = False
        self._observations: dict[str, Any] = {}
        try:
            self._simulator = factory(str(self.scene_path))
            self._observations = self._simulator.get_sensor_observations()
        except Exception:
            self.close()
            raise

    @property
    def closed(self) -> bool:
        """Whether the simulator has been closed."""

        return self._closed

    def close(self) -> None:
        """Close the Habitat-Sim instance exactly once."""

        if self._closed:
            return
        simulator = self._simulator
        self._simulator = None
        self._closed = True
        if simulator is not None:
            simulator.close()

    def __enter__(self) -> HabitatEnvAdapter:
        """Return this open adapter for scoped simulator ownership."""

        if self._closed:
            raise RuntimeError("cannot enter a closed Habitat environment")
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: Any,
    ) -> None:
        """Always close the simulator when leaving the context."""

        del exception_type, exception, traceback
        self.close()

    @property
    def position(self) -> dict[str, float]:
        """Return the current Habitat agent position in scene coordinates."""

        agent_state = self._agent_state()
        return {
            "x": float(agent_state.position[0]),
            "y": float(agent_state.position[1]),
            "z": float(agent_state.position[2]),
        }

    @property
    def rotation_yaw(self) -> float:
        """Return current yaw in degrees from the Habitat agent quaternion."""

        rotation = self._agent_state().rotation
        w = float(rotation.real)
        x, y, z = (float(value) for value in rotation.imag)
        yaw = math.degrees(
            math.atan2(
                2.0 * (w * y + x * z),
                1.0 - 2.0 * (y * y + z * z),
            )
        )
        return (yaw + 180.0) % 360.0 - 180.0

    @property
    def rgb_observation(self) -> Any:
        """Return the most recent uint8 RGBA color observation."""

        try:
            return self._observations["rgb"]
        except KeyError as error:
            raise RuntimeError("Habitat-Sim did not provide the rgb sensor") from error

    @property
    def done(self) -> bool:
        """Whether STOP has terminated this execution demo."""

        return self._done

    @property
    def success(self) -> bool:
        """Remain false because this adapter has no navigation goal."""

        return False

    def execute(self, action: HabitatAction) -> None:
        """Execute one mapped movement action in Habitat-Sim."""

        if self._done:
            raise RuntimeError("cannot execute an action after the episode is done")

        try:
            normalized_action = HabitatAction(action)
        except ValueError as error:
            raise ValueError(f"unsupported atomic action: {action!r}") from error

        if normalized_action is HabitatAction.STOP:
            self._done = True
            return

        habitat_action = self._ACTION_MAPPING[normalized_action]
        simulator = self._require_simulator()
        self._observations = simulator.step(habitat_action)

    def _agent_state(self) -> Any:
        simulator = self._require_simulator()
        return simulator.get_agent(0).get_state()

    def _require_simulator(self) -> Any:
        if self._simulator is None:
            raise RuntimeError("Habitat environment is closed")
        return self._simulator

import subprocess
import sys
import types
import unittest
from unittest import mock

from navida_habitat.action_chunk import HabitatAction


class FakeRotation:
    real = 1.0
    imag = (0.0, 0.0, 0.0)


class FakeAgentState:
    position = (1.0, 2.0, 3.0)
    rotation = FakeRotation()


class FakeAgent:
    def get_state(self) -> FakeAgentState:
        return FakeAgentState()


class FakeSimulator:
    def __init__(self) -> None:
        self.actions: list[str] = []
        self.close_count = 0
        self.rgb = object()

    def get_sensor_observations(self) -> dict[str, object]:
        return {"rgb": self.rgb}

    def get_agent(self, agent_id: int) -> FakeAgent:
        if agent_id != 0:
            raise AssertionError(f"unexpected agent id: {agent_id}")
        return FakeAgent()

    def step(self, action: str) -> dict[str, object]:
        self.actions.append(action)
        self.rgb = object()
        return {"rgb": self.rgb}

    def close(self) -> None:
        self.close_count += 1


class HabitatLazyImportTests(unittest.TestCase):
    def test_mock_and_adapter_modules_import_without_habitat(self) -> None:
        code = """
import builtins

real_import = builtins.__import__

def import_without_habitat(name, *args, **kwargs):
    if name == "habitat_sim" or name.startswith("habitat_sim."):
        raise AssertionError("habitat_sim must be imported lazily")
    return real_import(name, *args, **kwargs)

builtins.__import__ = import_without_habitat

import navida_habitat.action_chunk
import navida_habitat.mock_backend
import navida_habitat.mock_env
import navida_habitat.episode_runner
import navida_habitat.habitat_env
"""
        completed = subprocess.run(
            [sys.executable, "-c", code],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)


class HabitatEnvAdapterTests(unittest.TestCase):
    def test_configures_rgb_sensor_and_atomic_action_scales(self) -> None:
        from navida_habitat.habitat_env import HabitatEnvAdapter

        class SimulatorConfiguration:
            scene_id = ""

        class CameraSensorSpec:
            pass

        class AgentConfiguration:
            def __init__(self) -> None:
                self.sensor_specifications: list[object] = []
                self.action_space: dict[str, object] = {}

        class ActuationSpec:
            def __init__(self, *, amount: float) -> None:
                self.amount = amount

        class ActionSpec:
            def __init__(self, name: str, actuation: ActuationSpec) -> None:
                self.name = name
                self.actuation = actuation

        class Configuration:
            def __init__(self, sim_cfg: object, agents: list[object]) -> None:
                self.sim_cfg = sim_cfg
                self.agents = agents

        simulator = FakeSimulator()
        captured: dict[str, object] = {}

        def create_simulator(configuration: object) -> FakeSimulator:
            captured["configuration"] = configuration
            return simulator

        fake_habitat_sim = types.ModuleType("habitat_sim")
        fake_habitat_sim.SimulatorConfiguration = SimulatorConfiguration
        fake_habitat_sim.CameraSensorSpec = CameraSensorSpec
        fake_habitat_sim.SensorType = types.SimpleNamespace(COLOR="color")
        fake_habitat_sim.SensorSubType = types.SimpleNamespace(PINHOLE="pinhole")
        fake_habitat_sim.agent = types.SimpleNamespace(
            AgentConfiguration=AgentConfiguration,
            ActuationSpec=ActuationSpec,
            ActionSpec=ActionSpec,
        )
        fake_habitat_sim.Configuration = Configuration
        fake_habitat_sim.Simulator = create_simulator

        with mock.patch.dict(sys.modules, {"habitat_sim": fake_habitat_sim}):
            environment = HabitatEnvAdapter(scene_path="scene.glb")

        configuration = captured["configuration"]
        self.assertEqual(configuration.sim_cfg.scene_id, "scene.glb")
        agent_configuration = configuration.agents[0]
        sensor = agent_configuration.sensor_specifications[0]
        self.assertEqual(sensor.uuid, "rgb")
        self.assertEqual(sensor.sensor_type, "color")
        self.assertEqual(sensor.sensor_subtype, "pinhole")
        self.assertEqual(sensor.resolution, [128, 128])
        self.assertEqual(sensor.position, [0.0, 1.5, 0.0])
        self.assertEqual(
            {
                name: action_spec.actuation.amount
                for name, action_spec in agent_configuration.action_space.items()
            },
            {"move_forward": 0.25, "turn_left": 15.0, "turn_right": 15.0},
        )
        environment.close()

    def test_maps_navigation_actions_to_habitat_sim(self) -> None:
        from navida_habitat.habitat_env import HabitatEnvAdapter

        simulator = FakeSimulator()
        environment = HabitatEnvAdapter(
            scene_path="scene.glb",
            simulator_factory=lambda scene_path: simulator,
        )

        environment.execute(HabitatAction.MOVE_FORWARD)
        environment.execute(HabitatAction.TURN_LEFT)
        environment.execute(HabitatAction.TURN_RIGHT)

        self.assertEqual(
            simulator.actions,
            ["move_forward", "turn_left", "turn_right"],
        )

    def test_stop_finishes_without_claiming_navigation_success(self) -> None:
        from navida_habitat.habitat_env import HabitatEnvAdapter

        simulator = FakeSimulator()
        environment = HabitatEnvAdapter(
            scene_path="scene.glb",
            simulator_factory=lambda scene_path: simulator,
        )

        returned_value = environment.execute(HabitatAction.STOP)

        self.assertIsNone(returned_value)
        self.assertTrue(environment.done)
        self.assertFalse(environment.success)
        self.assertEqual(simulator.actions, [])
        with self.assertRaisesRegex(RuntimeError, "after the episode is done"):
            environment.execute(HabitatAction.MOVE_FORWARD)

    def test_exposes_real_agent_state_and_current_rgb_observation(self) -> None:
        from navida_habitat.habitat_env import HabitatEnvAdapter

        simulator = FakeSimulator()
        environment = HabitatEnvAdapter(
            scene_path="scene.glb",
            simulator_factory=lambda scene_path: simulator,
        )
        initial_rgb = environment.rgb_observation

        environment.execute(HabitatAction.MOVE_FORWARD)

        self.assertEqual(
            environment.position,
            {"x": 1.0, "y": 2.0, "z": 3.0},
        )
        self.assertEqual(environment.rotation_yaw, 0.0)
        self.assertIs(environment.rgb_observation, simulator.rgb)
        self.assertIsNot(environment.rgb_observation, initial_rgb)

    def test_close_is_idempotent(self) -> None:
        from navida_habitat.habitat_env import HabitatEnvAdapter

        simulator = FakeSimulator()
        environment = HabitatEnvAdapter(
            scene_path="scene.glb",
            simulator_factory=lambda scene_path: simulator,
        )

        environment.close()
        environment.close()

        self.assertEqual(simulator.close_count, 1)
        self.assertTrue(environment.closed)

    def test_context_manager_closes_after_an_exception(self) -> None:
        from navida_habitat.habitat_env import HabitatEnvAdapter

        simulator = FakeSimulator()
        environment = HabitatEnvAdapter(
            scene_path="scene.glb",
            simulator_factory=lambda scene_path: simulator,
        )

        with self.assertRaisesRegex(RuntimeError, "episode failed"):
            with environment as entered_environment:
                self.assertIs(entered_environment, environment)
                raise RuntimeError("episode failed")

        self.assertEqual(simulator.close_count, 1)
        self.assertTrue(environment.closed)

    def test_initialization_failure_closes_created_simulator(self) -> None:
        from navida_habitat.habitat_env import HabitatEnvAdapter

        class FailingObservationSimulator(FakeSimulator):
            def get_sensor_observations(self) -> dict[str, object]:
                raise RuntimeError("initial RGB failed")

        simulator = FailingObservationSimulator()

        with self.assertRaisesRegex(RuntimeError, "initial RGB failed"):
            HabitatEnvAdapter(
                scene_path="scene.glb",
                simulator_factory=lambda scene_path: simulator,
            )

        self.assertEqual(simulator.close_count, 1)


if __name__ == "__main__":
    unittest.main()

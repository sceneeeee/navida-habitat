"""Configuration/CLI unit tests with explicit fakes, never a Habitat smoke test.

Load the real adapter and CLI modules while replacing only unavailable Habitat
imports and environment/runner boundaries. No simulator action is executed;
these tests cannot measure displacement or validate a Habitat installation.
"""

import importlib.util
from contextlib import nullcontext
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest

# Preload outside patch.dict so the real NumPy module is never rolled back.
importlib.import_module("numpy")
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
INVALID = (float('nan'), float('inf'), float('-inf'), 0.0, -1.0)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    # dataclasses needs its module in sys.modules; restore it after loading.
    with mock.patch.dict(sys.modules, {name: module}):
        spec.loader.exec_module(module)
    return module


def fake_config(simulator=None):
    def sensor():
        return SimpleNamespace(width=256, height=256, hfov=90)
    if simulator is None:
        simulator = SimpleNamespace(forward_step_size=0.5, turn_angle=10)
    simulator.agents = SimpleNamespace(main_agent=SimpleNamespace(
        sim_sensors=SimpleNamespace(rgb_sensor=sensor(), depth_sensor=sensor())
    ))
    return SimpleNamespace(habitat=SimpleNamespace(
        simulator=simulator, dataset=SimpleNamespace()
    ))


class EvaluatorConfigurationTest(unittest.TestCase):
    def setUp(self):
        habitat = ModuleType('habitat')
        habitat.get_config = mock.Mock(return_value=fake_config())
        habitat.Env = mock.Mock(return_value=SimpleNamespace(close=mock.Mock()))
        config_module = ModuleType('habitat.config')
        config_module.read_write = lambda config: nullcontext(config)
        actions = ModuleType('habitat.sims.habitat_simulator.actions')
        actions.HabitatSimActions = SimpleNamespace(
            turn_left=2, turn_right=3, move_forward=1, stop=0
        )
        # Deliberate import substitutes, scoped to adapter loading only.
        with mock.patch.dict(sys.modules, {
            'habitat': habitat, 'habitat.config': config_module,
            'habitat.sims.habitat_simulator.actions': actions,
        }):
            self.adapter = load_module('audit_habitat_env',
                                       'habitat_vln/envs/habitat_env.py')
        self.habitat = habitat
        self.assertFalse(
            "habitat" in sys.modules and sys.modules["habitat"] is habitat
        )
        self.scheduler = load_module('habitat_vln.runtime._config_test_scheduler',
                                     'habitat_vln/runtime/scheduler.py')

    def load_cli(self, demo=False):
        # Environment exports and runner are explicit fake boundaries. The real
        # build_env adapter is retained so CLI -> config wiring is exercised.
        envs = mock.MagicMock(name='FAKE_env_exports')
        envs.build_env = self.adapter.build_env
        runtime = mock.MagicMock(name='FAKE_runtime_exports')
        runtime.validate_frequencies = self.scheduler.validate_frequencies
        runtime.resolve_frequency_mode = self.scheduler.resolve_frequency_mode
        with mock.patch.dict(sys.modules, {
            'habitat_vln.envs': envs, 'habitat_vln.runtime': runtime,
        }):
            if demo:
                module = load_module('habitat_vln.demos._config_test_demo',
                    'habitat_vln/demos/run_grounded_navida_demo.py')
            else:
                module = load_module('habitat_vln._config_test_cli',
                    'habitat_vln/habitat_vln_nav.py')
        return module, runtime

    def test_adapter_corrects_mismatched_geometry_before_initialization(self):
        self.adapter.build_env(paper_pure=True)
        config = self.habitat.Env.call_args.kwargs['config']
        self.assertEqual(config.habitat.simulator.forward_step_size, 0.25)
        self.assertEqual(config.habitat.simulator.turn_angle, 15)

    def test_adapter_default_preserves_non_navida_geometry(self):
        self.adapter.build_env()
        config = self.habitat.Env.call_args.kwargs['config']
        self.assertEqual(config.habitat.simulator.forward_step_size, 0.5)
        self.assertEqual(config.habitat.simulator.turn_angle, 10)

    def test_geometry_check_rejects_a_config_that_ignores_injection(self):
        class IgnoredGeometry(SimpleNamespace):
            def __setattr__(self, key, value):
                if key != self.ignored_key:
                    super().__setattr__(key, value)

        for field in ('forward_step_size', 'turn_angle'):
            with self.subTest(field=field):
                # Start with mismatched values; silently ignore one config write.
                simulator = IgnoredGeometry(
                    ignored_key=field,
                    **{field: 0.5 if field == 'forward_step_size' else 10}
                )
                self.habitat.get_config.return_value = fake_config(simulator)
                with self.assertRaisesRegex(ValueError, 'turn_angle=15'):
                    self.adapter.build_env(paper_pure=True)
                self.habitat.Env.assert_not_called()

    def test_normal_cli_injects_only_for_official_http(self):
        cli, runtime = self.load_cli()
        for official in (False, True):
            with self.subTest(official=official), tempfile.TemporaryDirectory() as d:
                self.habitat.get_config.return_value = fake_config()
                argv = ['cli', '--output-dir', d]
                argv += ['--official-navida-http'] if official else ['--mock-policy']
                with mock.patch.object(sys, 'argv', argv):
                    cli.main()
                sim = self.habitat.Env.call_args.kwargs['config'].habitat.simulator
                self.assertEqual(sim.forward_step_size, 0.25 if official else 0.5)
                self.assertEqual(sim.turn_angle, 15 if official else 10)
        self.assertEqual(runtime.run_navigation.call_count, 2)

    def test_grounded_cli_injects_geometry(self):
        demo, runtime = self.load_cli(demo=True)
        with tempfile.TemporaryDirectory() as d:
            dataset = Path(d) / 'existing.json.gz'
            dataset.touch()
            demo.main(['--dataset-path', str(dataset)])
        sim = self.habitat.Env.call_args.kwargs['config'].habitat.simulator
        self.assertEqual((sim.forward_step_size, sim.turn_angle), (0.25, 15))
        runtime.run_navigation.assert_called_once()

    def test_scheduler_rejects_all_invalid_frequency_fields(self):
        for field in ('vision_hz', 'inference_hz', 'joint_hz'):
            for value in INVALID:
                args = SimpleNamespace(vision_hz=5., inference_hz=1., joint_hz=1.,
                                       frequency_mode='joint', qwen_role='controller')
                setattr(args, field, value)
                with self.subTest(field=field, value=value):
                    with self.assertRaisesRegex(ValueError, 'finite'):
                        self.scheduler.validate_frequencies(args)

    def test_advance_rejects_invalid_rate_without_entering_loop(self):
        for value in INVALID:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.scheduler.advance_inference_time(0., value, 0.)
        self.assertEqual(self.scheduler.advance_inference_time(0., 0.5, 2.), 4.)

    def test_grounded_rejects_invalid_frequency_before_environment_creation(self):
        demo, runtime = self.load_cli(demo=True)
        for field in ('joint_hz', 'video_fps'):
            for value in INVALID:
                args = demo.parse_args([])
                setattr(args, field, value)
                with self.subTest(field=field, value=value):
                    with mock.patch.object(demo, 'parse_args', return_value=args):
                        with self.assertRaisesRegex(ValueError, 'finite'):
                            demo.main([])
        self.habitat.get_config.assert_not_called()
        runtime.run_navigation.assert_not_called()
        demo._validate_args(demo.parse_args([]))


if __name__ == '__main__':
    unittest.main()

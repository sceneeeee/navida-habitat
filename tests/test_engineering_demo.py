"""Fake sequence/queue contract; no scene or learned model is involved."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location('engineering_demo',
    Path(__file__).resolve().parents[1] / 'scripts/run_engineering_demo.py')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)

class EngineeringDemoTest(unittest.TestCase):
    def test_showcase_is_bounded_and_stops_after_twenty_motion_actions(self):
        actions = [a for chunk in demo.SHOWCASE for a in chunk]
        self.assertEqual(len(actions), 21)
        self.assertEqual(actions[-1], 'stop')
        self.assertNotIn('stop', actions[:-1])

    def test_fixed_decisions_and_invalid_case_do_not_invent_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            policy = demo.FakePolicy(Path(directory), mode='invalid')
            policy.reset('test')
            first = policy.act(instruction='ignored', decision_step=0)
            invalid = policy.act(instruction='ignored', decision_step=1)
        self.assertEqual(first.atomic_actions, ('turn_left', 'turn_left'))
        self.assertFalse(invalid.valid)
        self.assertEqual(invalid.atomic_actions, ())
        self.assertIn('fake', invalid.metadata['policy_source'])

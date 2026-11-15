"""Transparent audit around real CLI/Env/client; no fake transport or Env."""
import argparse, hashlib, json, runpy, sys
from pathlib import Path
import cv2, habitat, numpy as np
from omegaconf import OmegaConf
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from habitat_vln import envs
from habitat_vln.policies import OfficialNaVIDAHTTPPolicy
from habitat_vln.runtime import navigation_runner as runner
from habitat_vln.runtime.artifacts import rgb_to_bgr
p = argparse.ArgumentParser()
p.add_argument('--case-dir', required=True)
(a, args) = p.parse_known_args()
root = Path(a.case_dir)
raw = root / 'raw_rgb'
raw.mkdir()

def log(kind, **values):
    with (root / 'habitat-audit.jsonl').open('a') as f:
        f.write(json.dumps(dict(kind=kind, **values)) + '\n')

def snapshot(env):
    s = env.sim.get_agent_state()
    q = s.rotation
    return dict(position=s.position.tolist(), quaternion_xyzw=[q.x, q.y, q.z, q.w], metrics=env.get_metrics(), episode_over=bool(env.episode_over))
original_build = envs.build_env
real_env = None

def build(**kwargs):
    global real_env
    e = original_build(**kwargs)
    assert isinstance(e, habitat.Env)
    real_env = e
    OmegaConf.save(e._config, root / 'effective-config.yaml')
    log('build', geometry=dict(forward_step_size=e.sim.habitat_config.forward_step_size, turn_angle=e.sim.habitat_config.turn_angle))
    original_reset = e.reset
    original_close = e.close

    def reset():
        obs = original_reset()
        log('reset', state=snapshot(e))
        return obs

    def close():
        try:
            terminal = snapshot(e)
            (root / 'terminal-state.json').write_text(json.dumps(terminal, indent=2))
            log('close', state=terminal)
        finally:
            original_close()
    e.reset = reset
    e.close = close
    return e
envs.build_env = build
original_step = runner.step_navigation_action
step_index = 0

def step(e, action):
    global step_index
    before = snapshot(e)
    try:
        obs = original_step(e, action)
    except Exception as exc:
        log('step_error', action=action, before=before, error=repr(exc))
        raise
    log('step', step=step_index, action=action, before=before, after=snapshot(e), collision=bool(e.sim.previous_step_collided))
    step_index += 1
    return obs
runner.step_navigation_action = step
original_predict = OfficialNaVIDAHTTPPolicy.predict

def predict(self, observation):
    rgb = np.asarray(observation.rgb)
    path = raw / f'observation_{observation.step:03d}.png'
    assert cv2.imwrite(str(path), rgb_to_bgr(rgb))
    info = dict(step=observation.step, rgb_pixels_sha256=hashlib.sha256(rgb.tobytes()).hexdigest(), shape=list(rgb.shape), rgb_path=str(path), depth_is_none=observation.depth is None, context_keys=sorted(observation.navigation_context))
    output = original_predict(self, observation)
    log('predict', **info, action=output.action, valid=output.is_valid, termination_reason=output.termination_reason, metadata=output.metadata)
    return output
OfficialNaVIDAHTTPPolicy.predict = predict
sys.argv = ['habitat_vln.demos.run_grounded_navida_demo'] + [x for x in args if x != '--']
runpy.run_module('habitat_vln.demos.run_grounded_navida_demo', run_name='__main__')

"""Python3.10 real TCP server + Python3.9 real Habitat CLI, deterministic fake policy."""
import argparse, base64, contextlib, hashlib, json, os, socket, subprocess, sys, threading, traceback
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.request import urlopen
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from navida_habitat.http_service import create_http_server

def parse_args():
    p = argparse.ArgumentParser(description='Real Habitat/TCP engineering demo, deterministic Fake Policy only.')
    p.add_argument('--habitat-python', required=True, type=Path)
    p.add_argument('--scenes-dir', required=True, type=Path)
    p.add_argument('--output-dir', type=Path, default=Path('outputs/engineering-demo'))
    p.add_argument('--case', choices=['showcase', 'normal', 'invalid'], default='showcase')
    p.add_argument('--video-fps', type=float, default=2.0)
    p.add_argument('--gpu-device-id', type=int, default=-1)
    args = p.parse_args()
    if not 0 < args.video_fps <= 60:
        p.error('video-fps must be finite in (0,60]')
    return args
SHOWCASE = [('turn_left', 'turn_left'), ('turn_right', 'turn_right'), ('move_forward', 'move_forward'), ('turn_left', 'turn_left'), ('move_forward', 'move_forward'), ('turn_right', 'turn_right'), ('move_forward', 'move_forward'), ('turn_right', 'turn_right'), ('move_forward', 'move_forward'), ('turn_left', 'turn_left'), ('stop',)]

def write(path, value):
    path.write_text(json.dumps(value, indent=2))

def readlines(path):
    return [json.loads(x) for x in path.read_text().splitlines()]

class FakePolicy:

    def __init__(self, case, mode='showcase'):
        self.case = case
        self.mode = mode
        self.closed = 0
        self.current = {}
        self.observations = 0
        self.decisions = 0

    def log(self, kind, **values):
        with (self.case / 'http.jsonl').open('a') as f:
            f.write(json.dumps(dict(kind=kind, **values)) + '\n')

    def reset(self, episode_id):
        self.episode = episode_id
        self.log('policy_reset', episode_id=episode_id)

    def observe(self, rgb):
        self.observations += 1
        self.log('decoded_rgb', simulator_step=self.current['simulator_step'], mode=rgb.mode, size=list(rgb.size), pixels_sha256=hashlib.sha256(rgb.tobytes()).hexdigest())

    def act(self, *, instruction, decision_step):
        self.decisions += 1
        if self.mode == 'showcase':
            actions = SHOWCASE[decision_step]
            raw = 'fixed actions: ' + ','.join(actions)
            valid = True
        elif decision_step == 0:
            actions = ('turn_left', 'turn_left')
            raw = 'turn left 30 degree'
            valid = True
        elif self.mode == 'invalid':
            actions = ()
            raw = 'INVALID_FAKE_OUTPUT'
            valid = False
        elif decision_step == 1:
            actions = ('move_forward',)
            raw = 'forward 25 cm'
            valid = True
        else:
            actions = ('stop',)
            raw = 'stop'
            valid = True
        self.log('fake_decision', decision_step=decision_step, atomic_actions=actions, valid=valid)
        return SimpleNamespace(decision_step=decision_step, raw_output=raw, valid=valid, error=None if valid else 'deterministic fake invalid decision', latency_seconds=0.0, atomic_actions=actions, metadata={'policy_source': 'deterministic_fake_policy', 'case': self.case.name, 'benchmark_comparable': False})

    def close(self):
        self.closed += 1
        self.log('policy_close', close_count=self.closed)

@contextlib.contextmanager
def server_context(case, mode='showcase'):
    fake = FakePolicy(case, mode)
    server = create_http_server(policy=fake, host='127.0.0.1', port=0)
    original_start = server.service.start_episode
    original_process = server.service.process_step

    def start(payload):
        response = original_start(payload)
        fake.log('episode_start', request=payload, response=response)
        return response

    def process(payload):
        fake.current = payload
        fake.log('request', episode_id=payload['episode_id'], simulator_step=payload['simulator_step'], fields=sorted(payload), instruction=payload['instruction'], png_bytes=len(base64.b64decode(payload['rgb_png_base64'])))
        response = original_process(payload)
        fake.log('response', **response)
        return response
    server.service.start_episode = start
    server.service.process_step = process
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    (host, port) = server.server_address
    url = f'http://{host}:{port}'
    life = {'url': url, 'policy_source': 'deterministic_fake_policy'}
    try:
        with urlopen(url + '/health', timeout=5) as response:
            life['health'] = json.load(response)
        assert life['health']['protocol'] == 'paper_pure'
        yield (fake, url)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
        life.update(thread_alive=thread.is_alive(), policy_close_count=fake.closed, observations=fake.observations, decisions=fake.decisions)
        with socket.socket() as probe:
            probe.settimeout(1)
            life['port_closed'] = probe.connect_ex((host, port)) != 0
        write(case / 'lifecycle.json', life)
        assert not thread.is_alive() and fake.closed == 1 and life['port_closed']

def main():
    ARGS = parse_args()
    run = ARGS.output_dir.resolve() / datetime.now(timezone.utc).strftime('run_%Y%m%dT%H%M%SZ')
    run.mkdir(parents=True)
    case = run / ARGS.case
    case.mkdir()
    summary = {'policy_source': 'deterministic_fake_policy', 'case': ARGS.case, 'logical_tick_hz': 1.0, 'video_fps': ARGS.video_fps, 'wall_clock_paced': False, 'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(), 'source_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=REPO))}
    prepare = [str(ARGS.habitat_python), '-c', "import sys,habitat;from omegaconf import OmegaConf;from habitat_vln.data.create_grounded_demo_episode import build_payload;import gzip,json;p=build_payload();p['episodes'][0]['episode_id']='engineering-fake-'+sys.argv[1];p['episodes'][0]['info'].update(policy_source='deterministic_fake_policy',dataset_scope='engineering_demo',benchmark_comparable=False);f=gzip.open(sys.argv[2],'wt');json.dump(p,f);f.close();c=habitat.get_config('benchmark/nav/pointnav/pointnav_hm3d.yaml');ctx=habitat.config.read_write(c);ctx.__enter__();c.habitat.environment.max_episode_steps=24;c.habitat.environment.max_episode_seconds=90;ctx.__exit__(None,None,None);OmegaConf.save(c,sys.argv[3])", ARGS.case, str(case / 'episode.json.gz'), str(case / 'task.yaml')]
    subprocess.run(prepare, cwd=REPO, check=True, timeout=30)
    try:
        with server_context(case, ARGS.case) as (fake, url):
            command = [str(ARGS.habitat_python), '-u', str(REPO / 'habitat_vln/demos/engineering_client.py'), '--case-dir', str(case), '--', '--task-config', str(case / 'task.yaml'), '--dataset-path', str(case / 'episode.json.gz'), '--scenes-dir', str(ARGS.scenes_dir.resolve()), '--official-navida-url', url, '--official-navida-timeout', '10', '--num-episodes', '1', '--max-steps', '24', '--width', '640', '--height', '480', '--gpu-device-id', str(ARGS.gpu_device_id), '--video-fps', str(ARGS.video_fps), '--no-rate-limit', '--output-dir', str(case / 'outputs')]
            write(case / 'command.json', command)
            with (case / 'runner.log').open('w') as log:
                completed = subprocess.run(command, cwd=REPO, stdout=log, stderr=subprocess.STDOUT, timeout=180, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            if completed.returncode:
                raise RuntimeError('CLI failed: see runner.log')
        output = next((case / 'outputs').glob('run_*'))
        episode = json.loads((output / 'episode_summary.json').read_text())
        summary.update(output_dir=str(output), episode_failed=episode['failed'], video_generated=episode['video_generated'])
        if ARGS.case != 'invalid' and (episode['failed'] or not episode['stopped']):
            raise RuntimeError('Fixed sequence did not finish with STOP; see original artifacts')
    except Exception:
        summary['error'] = traceback.format_exc()
        traceback.print_exc()
    finally:
        write(run / 'execution.json', summary)
        print('DEMO_RUN', run, flush=True)
    return 1 if summary.get('error') else 0
if __name__ == '__main__':
    sys.exit(main())

"""Export small presentation assets from measured data; never run a simulator."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--asset-dir', type=Path, default=Path('docs/assets'))
    args = parser.parse_args()
    root, assets = args.run_dir, args.asset_dir
    assets.mkdir(parents=True, exist_ok=True)
    execution = json.loads((root / 'execution.json').read_text())
    assert execution['policy_source'] == 'deterministic_fake_policy'
    case = root / 'showcase'
    out = Path(execution['output_dir'])
    events = [json.loads(s) for s in (case / 'habitat-audit.jsonl').read_text().splitlines()]
    steps = [s for s in events if s['kind'] == 'step']
    predictions = [s for s in events if s['kind'] == 'predict']
    initial = next(s['state'] for s in events if s['kind'] == 'reset')
    terminal = json.loads((case / 'terminal-state.json').read_text())
    http = [json.loads(s) for s in (case / 'http.jsonl').read_text().splitlines()]
    responses = [s for s in http if s['kind'] == 'response']
    decoded = [s for s in http if s['kind'] == 'decoded_rgb']
    rows = list(csv.DictReader((out / 'trajectory.csv').open()))
    assert len(steps) == len(rows) == len(responses) == len(predictions) == 21
    for index, (step, response, row, rgb, prediction) in enumerate(zip(steps, responses, rows, decoded, predictions)):
        assert step['action'] == response['action'] == row['executed_action']
        assert response['simulator_step'] == index
        assert rgb['pixels_sha256'] == prediction['rgb_pixels_sha256']
        assert response['decision_step'] == index // 2
        assert response['inferred'] == (index % 2 == 0)
    summary = json.loads((out / 'episode_summary.json').read_text())
    assert summary['stopped'] and not summary['failed']
    assert summary['final_pose']['position'] == terminal['position']
    assert summary['policy_source'] == 'deterministic_fake_policy'
    shutil.copy(case / 'raw_rgb/observation_000.png', assets / 'habitat-scene.png')
    states = [initial] + [s['after'] for s in steps]
    positions = np.array([s['position'] for s in states])
    fig, ax = plt.subplots(figsize=(7, 5), layout='constrained')
    ax.plot(positions[:, 0], -positions[:, 2], '-o', color='#2468b5', markersize=4)
    ax.scatter(*[positions[0, 0], -positions[0, 2]], s=100, color='#18844b', label='Start', zorder=4)
    ax.scatter(*[positions[-1, 0], -positions[-1, 2]], s=100, marker='X', color='#c35724', label='STOP', zorder=5)
    for i in (0, 6, 10, 14):
        ax.annotate(str(i), (positions[i, 0], -positions[i, 2]), xytext=(6, 6), textcoords='offset points')
    ax.set(xlabel='World X (m)', ylabel='World -Z (m)', title='Measured Habitat poses · Deterministic Fake Policy')
    ax.set_aspect('equal', adjustable='datalim'); ax.grid(alpha=.2); ax.legend(); ax.margins(.12)
    collisions = sum(s['collision'] for s in steps)
    ax.set_xlabel(f'World X (m)\n21 actual actions · {collisions} collisions · no learned navigation')
    fig.savefig(assets / 'habitat-trajectory.png', dpi=150); plt.close(fig)
    with (assets / 'showcase-poses.csv').open('w', newline='') as f:
        writer = csv.writer(f, lineterminator="\n"); writer.writerow(['state_after_step', 'x_m', 'y_m', 'z_m', 'qx', 'qy', 'qz', 'qw'])
        for index, state in enumerate(states): writer.writerow([index, *state['position'], *state['quaternion_xyzw']])
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="330" viewBox="0 0 1000 330">
<rect width="1000" height="330" rx="16" fill="#102238"/>
<g font-family="sans-serif" fill="white"><text x="30" y="42" font-size="22">Real Habitat + TCP HTTP · Deterministic Fake Policy</text>
<text x="30" y="69" font-size="14" fill="#9dc5ef">Design diagram; counts below come from the recorded showcase. No NaVIDA checkpoint.</text>
<g fill="#214567" stroke="#74b6ee"><rect x="30" y="102" width="205" height="110" rx="10"/>
<rect x="270" y="102" width="205" height="110" rx="10"/><rect x="510" y="102" width="205" height="110" rx="10"/>
<rect x="750" y="102" width="220" height="110" rx="10"/></g>
<g font-size="17"><text x="45" y="132">Habitat · Python 3.9</text><text x="285" y="132">HTTP client → server</text>
<text x="525" y="132">Server action queue</text><text x="765" y="132">Habitat Env.step</text></g>
<g font-size="14"><text x="45" y="163">640×480 real RGB</text><text x="45" y="190">Instruction + step ID</text>
<text x="285" y="163">Lossless PNG / JSON</text><text x="285" y="190">Python 3.10 service</text>
<text x="525" y="163">d0: left, left</text><text x="525" y="190">inferred: true, false</text>
<text x="765" y="163">Pose + RGB + metrics</text><text x="765" y="190">CSV / JSON / H.264</text></g>
<g font-size="26"><text x="242" y="162">→</text><text x="482" y="162">→</text><text x="722" y="162">→</text></g>
<text x="30" y="254" font-size="17">Observed: 21 requests → 11 fixed decisions → 21 actual actions → explicit STOP</text>
<text x="30" y="286" font-size="14" fill="#9dc5ef">First four decision IDs: 0, 0, 1, 1 · RGB observed every step · no fallback</text></g></svg>'''
    (assets / 'http-flow.svg').write_text(svg)
    video = assets / 'engineering-demo.mp4'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(out / 'run.mp4'),
                    '-vf', "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='Deterministic Fake Policy | real Habitat + TCP HTTP':x=12:y=h-32:fontsize=18:fontcolor=white:box=1:boxcolor=black@0.7",
                    '-an', '-c:v', 'libx264', '-crf', '24', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(video)], check=True, timeout=60)
    assert video.stat().st_size < 2 * 1024**2, 'Keep large video local, do not commit it'
    probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-show_entries',
                           'stream=codec_name,width,height,nb_read_frames,r_frame_rate:format=duration',
                           '-of', 'json', str(video)], check=True, capture_output=True, text=True)
    media = json.loads(probe.stdout); stream = media['streams'][0]
    assert stream['width'] == 640 and stream['height'] == 480 and stream['codec_name'] == 'h264'
    assert int(stream['nb_read_frames']) == 21
    evidence = dict(policy_source='deterministic_fake_policy',scene='skokloster-castle',
                    initial_pose=initial,final_pose=terminal,actions=[s['action'] for s in steps],
                    http_requests=21,decisions=11,collisions=collisions,
                    logical_tick_hz=1,wall_clock_paced=False,video_fps=execution['video_fps'],
                    media=media,first_decision_ids=[s['decision_step'] for s in responses[:4]],
                    source_commit=execution.get('source_commit', '2d99b01993632a797f6101e265a8ee02cbcf688d'),
                    provenance_note='Showcase ran with the uncommitted Demo/recording changes described in PR #8; source_commit is the base, not the final commit.')
    evidence['asset_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in assets.iterdir() if p.is_file() and p.name != 'showcase-evidence.json'}
    (assets / 'showcase-evidence.json').write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))

if __name__ == '__main__': main()

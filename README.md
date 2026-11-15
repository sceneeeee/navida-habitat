# NaVIDA–Habitat · SURF navigation systems engineering

[中文](README.zh-CN.md) · [Reproduce the Demo](docs/engineering-demo.md) · [Provenance](docs/evaluator-provenance.md) · [Historical validation](docs/validation-report.md)

Connect a visual-language navigation policy to Habitat through a strict,
stateful HTTP interface while keeping incompatible model and simulator stacks
in separate processes. Preserve every decision, executed action and terminal
state so a working pipeline can be distinguished from navigation success.

**Current status:** real Habitat 0.3.3 scene/reset, measured 25cm/15° actions,
and real TCP client/server/queue/Runner integration have passed. The showcase
below uses a **Deterministic Fake Policy**, not a NaVIDA checkpoint. No learned
navigation, paper reproduction or robot deployment is claimed.

## Real simulation showcase

![Real 640×480 Habitat RGB in skokloster-castle; fixed-action Fake Policy test](docs/assets/habitat-scene.png)

**[Watch the labelled 10.5-second Demo](docs/assets/engineering-demo.mp4)** ·
[Actual pose data](docs/assets/showcase-poses.csv) · [Evidence](docs/assets/showcase-evidence.json)

![Trajectory plotted from actual Habitat poses, not a planned path](docs/assets/habitat-trajectory.png)

One fixed start, one run: **21 actions, 21 HTTP requests, 11 fixed decisions,
0 collisions and explicit STOP**, at 640×480. Two queued actions share their
originating decision; every simulator step supplies a fresh real RGB frame.
Playback is 2 fps; logical control is 1 Hz with wall-clock pacing disabled.
These counts demonstrate execution and recording, not task-solving ability.

## Architecture and protocol

![HTTP request, decision queue and execution flow; counts from the measured run](docs/assets/http-flow.svg)

| Process | Responsibilities | Environment |
|---|---|---|
| Model/service | Checkpoint runtime or explicit test policy; RGB history; strict parser; episode state and action queue | Python 3.10 |
| Evaluator | Real Habitat RGB; lossless PNG/base64 HTTP client; unchanged valid actions; trajectory, metrics and media | Python 3.9, Habitat-Lab/Sim 0.3.3 |

`GET /health`, `POST /v1/episodes/start`, `POST /v1/steps` form the integration
seam. Episode reset clears history/queue. Queue consumption preserves
`decision_step` and sets `inferred=false`; only an empty queue requests another
decision. The model receives RGB/history/instruction, never privileged target
distance/bearing, simulator pose, depth, GPS or maps. `paper_pure` bypasses the
controller: invalid output terminates without random/forward fallback or
hidden Oracle/goal-distance STOP. Real checkpoint parsing selects at most two
sub-chunks and expands 25cm/15° actions. The Fake Policy directly supplies fixed
atomic actions and does not test learned inference or parser quality.

## What has actually been verified

| Evidence | Result | Boundary |
|---|---|---|
| Stage A | Real scene/navmesh/config/reset, RGB rendered through WSLg D3D12 | Local environment, no policy |
| Stage B | Forward **0.249999864m**, turns ≈15°, double-left ≈30°, STOP ended episode | Real measured motion |
| Stage C | Normal: 4 requests / 4 actions; invalid: 3 requests / **2 actions**, explicit failure | Real TCP and simulator; Fake Policy |
| Showcase | 640×480, 21 actions, H.264, CSV/JSON/raw RGB, terminal pose | Fixed sequence, not navigation reasoning |

Both Python suites and lightweight GitHub CI are run for this PR; CI itself
uses fakes and does **not** launch Habitat or download scenes/checkpoints.
[Demo guide](docs/engineering-demo.md) documents commands, versions, outputs and
recording semantics. Selected small presentation derivatives are versioned;
large raw recordings remain local/ignored.

## Reproduce without a checkpoint

Use already prepared independent environments and legally obtained test assets.
The scripts never install packages or download data automatically.

```bash
PYTHONDONTWRITEBYTECODE=1 timeout 240s /usr/bin/python3.10 scripts/run_engineering_demo.py \
  --habitat-python /home/evens/navida-stage-a/env/bin/python \
  --scenes-dir /home/evens/navida-stage-a/data/habitat-test-scenes \
  --output-dir outputs/engineering-demo
```

Replace paths and renderer device settings for another machine. The default
21-action sequence is bounded by 24 steps and 180 seconds; `--case invalid`
reproduces the failure path. No `/tmp` script is required. For authorized real
checkpoint inference, see the [model/evaluator quickstart](habitat_vln/README.md).
Do not install the Python 3.10 root package into the evaluator environment.

```bash
PYTHONPATH=src /usr/bin/python3.10 -m unittest discover -s tests -v
/home/evens/navida-stage-a/env/bin/python -m unittest discover -s test -v
```

## Historical NaVIDA experiments are separate

The SURF project has concluded. Historical checkpoint integration worked, but
its five-step PointNav smoke used an instruction unaligned with the random
goal. The later [team PR #5](https://github.com/RtimesC/habitat-lab/pull/5)
grounded test ran 80 real-checkpoint steps and stopped at the wrong location:
**success=0, SPL=0, final distance ≈8.620m**. A separate Oracle succeeded;
that is **not** NaVIDA success. Current Fake Policy media does not replace those
results. Future checkpoint replay, R2R/RxR benchmarks and robot work remain
separate, optional experiments.

## Contribution and reuse

The personal model-side runtime, parser, history, Policy API and HTTP service
were developed by sceneeeee/evenS with Codex assistance. Account-linked team
PRs [#4](https://github.com/RtimesC/habitat-lab/pull/4) and
[#5](https://github.com/RtimesC/habitat-lab/pull/5) added the evaluator HTTP
adapter and grounded Demo. The general evaluator framework came from the
**SURF team**, not solely the personal owner. The 35-file import is based on
`RtimesC/habitat-lab@835ac41e`; original blob hashes and subsequent differences
remain in the [manifest](docs/evaluator-source-manifest.json).

[Meta's original MIT notice](third_party/habitat-lab-MIT.LICENSE) is preserved.
No repository-wide license for personal model-side code has been selected.
NaVIDA, Habitat, scenes and datasets retain their respective authors/terms.
This repository does not redistribute weights, GLB/navmesh or datasets.
See the [contribution audit](docs/contribution-audit.md) and
[Chinese SURF closeout](docs/surf-closeout.zh-CN.md).

## Limits

One scene and a fixed Fake Policy test establish engineering behavior, not
generalization or navigation ability. CSV legacy pose/image are before-action,
metrics are after-action; `state_timing` makes this explicit and episode JSON
now records the final pose. Failed video generation reports a diagnostic;
detailed codec errors remain a possible follow-up. Semantic scene annotations,
real checkpoint replay and cross-platform rendering are not validated by this
showcase. [Legacy model-side README](docs/legacy-model-side-readme.zh-CN.md) is
retained as historical reference.

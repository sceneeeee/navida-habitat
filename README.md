# NaVIDA–Habitat | SURF Visual-Language Navigation Engineering

[中文版 README](README.zh-CN.md) · [中文结项报告](docs/surf-closeout.zh-CN.md) · [Evaluator quickstart](habitat_vln/README.md) · [Engineering case study](docs/portfolio-case-study.md) · [Contribution audit](docs/contribution-audit.md) · [Validation evidence](docs/validation-report.md)

**Status:** SURF concluded (2026). The original model-server / Habitat integration has historical real-checkpoint validation. This personal repository now contains an **extracted SURF evaluator application** as well as the model server. **The consolidated file layout has not yet been rerun with the live checkpoint and Habitat scene**, so the post-migration end-to-end path remains pending fresh verification.

## Project objective

Connect an official NaVIDA visual-language navigation checkpoint to Habitat so that simulated RGB observations and natural-language instructions produce auditable, bounded atomic navigation actions. Separate the model process from the simulator to allow different Python/CUDA stacks, avoid privileged simulator observations in the model policy, and retain traceable episode-level artifacts.

This is an **AI/robotics systems integration project**, not a claim of having invented or trained NaVIDA, reproduced its official paper results, or deployed on a physical robot.

## Architecture

~~~text
+------------------------ MODEL SERVICE ------------------------+
| Python 3.10, GPU, official NaVIDA checkpoint (4-bit in tests) |
| RGB frame history + instruction -> NaVIDA inference          |
|      -> strict action-chunk parser -> atomic action queue     |
| /health | /v1/episodes/start | /v1/steps (localhost HTTP)     |
+-------------------------------+------------------------------+
                                | JSON (RGB PNG/base64 request)
                                | one simulator action / response
+-------------------------------v------------------------------+
| Habitat evaluator application (Python 3.9, historical stack) |
| Fixed episode / scene / goal -> RGB observation              |
| OfficialNaVIDAHTTPPolicy -> paper_pure action                |
| Habitat env.step -> trajectory CSV / RGB frames / MP4        |
| Offline goal metrics and Oracle comparison (NOT model input) |
+--------------------------------------------------------------+
                    |
          External Meta Habitat-Lab / Habitat-Sim,
          with separately licensed scenes and datasets
~~~

**Protocol boundaries:** paper_pure uses current RGB, up to 8 sampled historical RGB frames, and the navigation instruction. The model receives no target distance/bearing, ground-truth pose, depth, GPS, compass or top-down map. Valid model actions are not overridden. Invalid output is reported and the evaluator should terminate without random fallback. The parser accepts up to 3 sub-chunks and executes at most the first 2, with 25 cm / 15-degree atomic steps. This intentionally differs from some upstream evaluator fallback behavior: it is **not a byte-identical official evaluation reproduction**.

## Engineering deliverables

| Component | Repository path | Evidence |
| --- | --- | --- |
| Strict parser, testable mock episode, JSONL trace | src/navida_habitat/action_chunk.py, episode_runner.py | [Personal PRs #1–2](https://github.com/sceneeeee/navida-habitat/pulls?q=is%3Apr+is%3Amerged) |
| Official checkpoint runtime, RGB history, multi-decision CLI | src/navida_habitat/model_runtime.py, frame_history.py, navida_backend.py | [Personal PR #3](https://github.com/sceneeeee/navida-habitat/pull/3) |
| Evaluator-facing Policy API and localhost HTTP server | src/navida_habitat/policy.py, http_service.py | [Personal PRs #5–6](https://github.com/sceneeeee/navida-habitat/pulls?q=is%3Apr+is%3Amerged) |
| Habitat-side HTTP policy adapter, protocol validation, client tests | habitat_vln/policies/official_navida_http_policy.py | [SURF team repo PR #4, authored by sceneeeee](https://github.com/RtimesC/habitat-lab/pull/4) |
| Grounded single-scene demo generator and runner | habitat_vln/data/create_grounded_demo_episode.py, demos/run_grounded_navida_demo.py | [SURF team repo PR #5, authored by sceneeeee](https://github.com/RtimesC/habitat-lab/pull/5) |
| Reusable evaluator environment, controller, runner, scheduling, logs, media | habitat_vln/envs, core, control, runtime | Extracted from the SURF team framework; **not exclusively personal authorship** |

The personal model-side repository was implemented and maintained by the account owner with Codex assistance, with no separate human collaborator in that repository according to the owner's clarification. The extracted general evaluator framework was part of **RtimesC's SURF team repository**. Its history and contributors remain separately credited; see [provenance](docs/evaluator-provenance.md).

## Historical results — two different experiments

| Evidence | Outcome | What it proves |
| --- | --- | --- |
| Model-side regression suite in [PR #6](https://github.com/sceneeeee/navida-habitat/pull/6) | 88 tests, 87 passed, one optional scene test skipped | Historical software regression, **not rerun here** |
| Real NaVIDA checkpoint on RTX 4060 Ti 8 GB | 4-bit inference; about 3.12 GiB peak **allocated** GPU memory | Resource-adapted local inference, not sustained/total memory |
| Five-step PointNav smoke, model service to Habitat | Five simulator steps with valid actions; instruction **not aligned** with random goal | Network/queue/simulator engineering connectivity, **not goal-directed navigation** |
| Grounded test-scene demo in [team PR #5](https://github.com/RtimesC/habitat-lab/pull/5) | **80 simulator steps; NaVIDA STOP at wrong location; success=0.0, SPL=0.0, final goal distance ~8.620m** | Goal-grounded single-episode **model failure**, while execution/log/media path worked |
| Separate Oracle control for the grounded demo | Oracle success=1.0, SPL=1.0 | Test episode/scene/metrics were executable; **this is not NaVIDA's result** |

None of these runs is a standardized R2R VLN-CE/RxR benchmark or supports generalization claims. No Jetson, ROS 2, FrogBot or other physical robot validation was completed during SURF. Evidence: [validation report](docs/validation-report.md).

## Quickstart — two processes, two environments

The personal model server uses **Python 3.10**. The migrated evaluator originally ran in a **separate Python 3.9 environment** with historical Habitat-Lab/Habitat-Sim. Do **not** force them into the same environment or assume the root pyproject.toml can install the evaluator into Python 3.9. Prepare simulator dependencies and legally obtained model/scene files separately.

**Terminal 1 — model server:**

~~~bash
# Python 3.10 model environment; run from this repository's root
export PYTHONPATH="$PWD/src"
python scripts/run_official_navida_http_server.py \
  --model-path /absolute/path/to/authorized/checkpoint \
  --host 127.0.0.1 --port 8008
~~~

**Terminal 2 — historical Habitat evaluator environment (Python 3.9):**

~~~bash
# Run from the same repository root after installing external Habitat dependencies
python -m habitat_vln.demos.run_grounded_navida_demo \
  --task-config benchmark/nav/pointnav/pointnav_hm3d.yaml \
  --scenes-dir /absolute/path/to/habitat-test-scenes \
  --official-navida-url http://127.0.0.1:8008 \
  --official-navida-timeout 900 \
  --gpu-device-id -1 --num-episodes 1 --max-steps 80 \
  --no-rate-limit --output-dir outputs/grounded_navida_demo
~~~

The demo creates a fixed single test episode locally if its default dataset does not yet exist, but requires the corresponding legal test scene/navmesh. The GPU device flag -1 is the historical WSLg workaround, not a universal setting. The exact task-config path and dependency versions must be verified against the installed historical Habitat-Lab environment. **These commands have not been replayed under the consolidated repository.**

Read the [full evaluator setup and test guidance](habitat_vln/README.md) before running.

## Tests

~~~bash
# Model environment (Python 3.10; mock and API regression)
PYTHONPATH=src python -m unittest discover -s tests -v

# Lightweight model-server ↔ evaluator-client HTTP contract (fake model, no scene)
PYTHONPATH=src python -m unittest discover -s tests -p 'test_evaluator_http_contract.py' -v

# Evaluator environment (Python 3.9 with historical dependencies)
python -m unittest discover -s test -p 'test_grounded_demo_episode.py' -v
python -m unittest discover -s test -p 'test_official_navida_http.py' -v
python -m unittest discover -s test -p 'test_grounded_navida_demo.py' -v
~~~

The new cross-process HTTP contract test uses a fake model policy and is **not** a real checkpoint or navigation benchmark. All tests listed here require actual execution after migration; no post-migration pass count is asserted. See the [acceptance checklist](docs/evaluator-migration-acceptance.md).

## Repository map

~~~text
src/navida_habitat/   Model runtime, RGB history, strict parser, HTTP server
scripts/              Model-side and mock CLI entrypoints
tests/                Model-side regression and cross-repository HTTP contract
habitat_vln/          SURF evaluator application extracted from team repository
test/                 Historical evaluator-side tests from the SURF snapshot
docs/                 Closeout, evidence, API contract, provenance, acceptance
third_party/          Historical source license notice
~~~

Original detailed Chinese model-side README is retained at [docs/legacy-model-side-readme.zh-CN.md](docs/legacy-model-side-readme.zh-CN.md). This document is an archived reference, not the current project status.

## Attribution, license and research integrity

The evaluator application was extracted from [RtimesC/habitat-lab at the merge of PR #5](https://github.com/RtimesC/habitat-lab/tree/835ac41e9ecf82c2c13b4bdf2f6747aef70860d6) (July 23, 2026). Its general-purpose framework came from the SURF team's codebase; the account owner also contributed specific evaluator adapter and grounded-demo modules through PRs #4 and #5. The extracted code is governed by the original MIT notice, preserved at [third_party/habitat-lab-MIT.LICENSE](third_party/habitat-lab-MIT.LICENSE). No repository-wide license for the personal model-side code has been selected; do not interpret the extracted-code notice as automatic relicensing of every file.

Meta Habitat-Lab/Habitat-Sim are independent upstream software; NaVIDA model architecture/checkpoint belong to their original authors; datasets and scenes may have additional terms. This repository does not redistribute external weights, licensed scenes, results or videos.

**The personal repository is a maintained derivative/integration of an original SURF team evaluator, not a claim to have solely authored the whole team project.** No formal benchmark or real robot experiment is implied by a historical integration or by this unverified migration.

# Habitat evaluator application — extracted SURF snapshot

This directory holds the **Habitat evaluator side** of the historical NaVIDA SURF integration. It was extracted from [RtimesC/habitat-lab @ 835ac41e](https://github.com/RtimesC/habitat-lab/tree/835ac41e9ecf82c2c13b4bdf2f6747aef70860d6) for independent **personal portfolio maintenance**, with [source attribution and MIT license](../docs/evaluator-provenance.md).

**Not a complete fork of Meta Habitat-Lab.** Install Habitat-Lab/Habitat-Sim externally. The application's setup requirements and some dependencies remain tied to the historical 2026-07 versions. Post-import changes are recorded in the provenance document.

## Two-process architecture

```text
Model server — Python 3.10                  Simulator/evaluator — Python 3.9
scripts/run_official_navida_http_server.py  habitat_vln/demos/run_grounded_navida_demo.py
   -> checkpoint runtime                       -> Habitat-Lab scene and goal
   -> RGB history / policy                     -> RGB observation and instruction
   -> strict action parser       <---HTTP--->  -> OfficialNaVIDAHTTPPolicy
   -> stateful action queue                    -> runner -> Habitat env.step
                                             -> trajectory.csv / RGB frames / video
```

**The evaluators do not pass privileged goal coordinates, shortest paths or target distance to the model in paper_pure mode.** The simulator may use goal data solely for offline evaluation and Oracle comparisons, not as policy observations.

## Migrated modules

- `habitat_vln/policies/official_navida_http_policy.py`: lossless RGB PNG transport, episode reset, strict response validation and no-fallback handling, originally authored by sceneeeee in evaluator [PR #4](https://github.com/RtimesC/habitat-lab/pull/4).
- `habitat_vln/data/create_grounded_demo_episode.py` and `demos/run_grounded_navida_demo.py`: fixed goal-linked single-scene demo generator and CLI, introduced in [PR #5](https://github.com/RtimesC/habitat-lab/pull/5).
- `habitat_vln/envs/`, `core/`, `control/`, `runtime/`: common evaluator framework from the team application, retaining the original source/provenance. Some runner and recorder changes were authored in PRs #4 and #5.
- `habitat_vln/evaluation/evaluate_pointnav_policies.py`: historical policy/Oracle comparison tooling; Oracle uses privileged shortest-path information and must remain separate from NaVIDA evaluation.
- `test/`: historical tests relevant to the migrated API and demo.

The historical app also retains some Qwen/NaVIDA policy modules imported by the common entrypoints. **Do not construe their presence as evidence of completed training, benchmark or model improvements.** Unrelated QLoRA training scripts and DoorNav B1 are excluded.

## External dependencies and runtime versions

- **Model terminal:** Python 3.10, original NaVIDA checkpoint with legitimate access, CUDA, PyTorch/Transformers and 4-bit dependencies, as documented in the repository root README.
- **Habitat terminal:** Python 3.9, the historical SURF evaluator environment `habitat_vlm`, Habitat-Lab/Habitat-Sim and CV/video dependencies. Original team `AGENTS.md` cited Habitat-Sim 0.3.3; model-side Stage 2 records describe a **different** local 0.2.4 setup. These must not be assumed interchangeable.
- A Habitat test scene (`skokloster-castle.glb` and navmesh) and necessary PointNav task configuration obtained through the lawful Habitat assets workflow.

**This migration does not install or download those dependencies.** A fresh clean-environment replay is still required before describing the personal repository as self-contained or runnable end-to-end.

## Historical grounded demo — optional replay, not executed in this migration

Terminal 1, from the repository root in the model environment:

```bash
export PYTHONPATH="$PWD/src"
python scripts/run_official_navida_http_server.py \
  --model-path /absolute/path/to/authorized/navida-checkpoint \
  --host 127.0.0.1 --port 8008
```

Terminal 2, from the **same repository root** but in the separate historical evaluator environment:

```bash
python -m habitat_vln.demos.run_grounded_navida_demo \
  --task-config benchmark/nav/pointnav/pointnav_hm3d.yaml \
  --scenes-dir /absolute/path/to/habitat-test-scenes \
  --official-navida-url http://127.0.0.1:8008 \
  --official-navida-timeout 900 \
  --num-episodes 1 --max-steps 80 \
  --gpu-device-id -1 --no-rate-limit \
  --output-dir outputs/grounded_navida_demo
```

Notes:
- `--gpu-device-id -1` is the original WSLg renderer workaround and is **not** correct for every machine.
- The default fixed dataset is created locally by the demo when missing; it references the external test scene and is **not** a benchmark sample.
- Task config discovery depends on the historical Habitat-Lab installation/version.
- The local model's response or navigation success may differ from the July 2026 experiment.
- Run scripts in their matching separate environments. Do not `pip install -e .` in the evaluator's Python 3.9 env because root `pyproject.toml` specifies Python 3.10.

## Testing (commands are suggestions; not run in this migration)

```bash
python -m unittest discover -s test -p 'test_grounded_demo_episode.py' -v
python -m unittest discover -s test -p 'test_official_navida_http.py' -v
python -m unittest discover -s test -p 'test_grounded_navida_demo.py' -v
python -m compileall -q habitat_vln test
```

These may require Habitat and CV dependencies. Record real results, dependency failures and later API changes in `temp_report.md`, which must never be committed.

**Historical PR #5 result:** one goal-aligned test scene, 80 simulator steps, NaVIDA model STOP at wrong location, success=0, SPL=0, final distance ~8.620m. A separate Oracle succeeded. These are historical **single-episode** engineering observations, not new results or standard VLN benchmark metrics.

See [SURF validation report](../docs/validation-report.md) and [contribution audit](../docs/contribution-audit.md).


## Post-import configuration checks (2026-11-12)

Both the ordinary CLI's `--official-navida-http` path and the Grounded Demo
explicitly request 0.25m forward / 15-degree turn configuration and check it
before Habitat construction. Ordinary non-NaVIDA and Oracle paths retain their
external config values. This aligns config with server action expansion; it is
**not a measurement of actual simulator motion**.

A lightweight configuration suite can run with Python 3.10, NumPy and Pillow:

```bash
PYTHONPATH=src python -m unittest discover -s tests -p 'test_evaluator_configuration.py' -v
```

It uses explicit Fake Config / environment / runner boundaries and tests both
CLI routes, default preservation, rejection of failed injection and invalid
frequencies. It does not install or validate Habitat. CI also runs this bounded
suite and triggers on `test/**`; it still does not run the Python 3.9 Habitat
regressions. The separate real-Habitat acceptance gates remain open.

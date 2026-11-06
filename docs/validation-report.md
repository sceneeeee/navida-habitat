# SURF validation evidence and limitations

Compiled: 2026-11-07. This is a retrospective audit, not a new experiment.

## Historical evidence

| Category | Historical observation | Source | Interpretation |
| --- | --- | --- | --- |
| Automated tests | 88 run: 87 passed, one optional integration test skipped | [PR #6](https://github.com/sceneeeee/navida-habitat/pull/6) | Original suite, not rerun today |
| Model inference | Official checkpoint on RTX 4060 Ti 8 GB, 4-bit | PR #6 | Local checkpoint was called successfully |
| Memory | Approximately 3.12 GiB peak **allocated** GPU memory | PR #6 | Not total, reserved, or steady-state memory |
| Habitat smoke | One random PointNav episode; five simulator steps | PR #6 | HTTP, parser, model, action queue and Habitat steps connected |
| Logging | trajectory.csv, RGB frames and MP4 generated during historical smoke | PR #6 | Artifacts are not available in this source repository |
| Parser audit | Three parsed sub-chunks, two selected, one ignored, with atomic action metadata | PR #6 | Recorded model-output to action conversion |

**Critical limit:** The manually supplied navigation instruction was not aligned to the random PointNav goal. This is an engineering smoke test, not a goal-grounded VLN episode. No success, SPL or other benchmark result may be claimed from it.

## Evidence provenance

- Source-code behavior was inspected through the GitHub repository, including HTTP service, policy, action parser, CLI and tests.
- Merged pull requests #1–#6 and the original Stage 2 technical record supply historical validation.
- Tests and checkpoint runs were **not repeated** during this documentation closeout. An attempted direct git clone from the execution container failed because the container could not resolve github.com; the GitHub connector was used to inspect and update source files instead.
- The current documentation changes do not demonstrate a fresh runtime or reproduction.

## Reproduction commands (not run in this closeout)

~~~bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests
git diff --check
~~~

The optional real-scene integration test additionally needs NAVIDA_HABITAT_RUN_INTEGRATION=1 and NAVIDA_HABITAT_SCENE plus its dependencies. A real checkpoint and Habitat evaluation additionally need legally accessed model weights, scenes, simulator setup and the paired evaluator repository.

## Missing evidence

- Goal/instruction-aligned full autonomous episodes and detailed stop/goal outcomes.
- Standard R2R VLN-CE / RxR protocol, held-out scenes, SR/SPL/NE and full baselines.
- Multi-episode performance statistics and controlled failure analysis.
- Jetson, ROS 2 or physical FrogBot deployments.
- A reproducible independent run in a newly prepared environment.

See [SURF closeout report](surf-closeout.zh-CN.md) for the final project boundary.

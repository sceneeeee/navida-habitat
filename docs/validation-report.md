# SURF validation evidence and limitations

Compiled: 2026-11-07. This is a retrospective audit, not a new experiment.

**Personal-repository consolidation update:** An evaluator application subset was copied unchanged from the RtimesC/habitat-lab merged PR #5 snapshot (835ac41e, July 23); 35 extracted source/test files matched their source Git blob hashes after the import. This is **file-integrity validation only**. Neither the new HTTP contract test nor the imported evaluator tests nor a real checkpoint/Habitat episode has been executed in the consolidated repository. See [migration acceptance checklist](evaluator-migration-acceptance.md).

## Historical evidence

| Category | Historical observation | Source | Interpretation |
| --- | --- | --- | --- |
| Automated tests | 88 run: 87 passed, one optional integration test skipped | [PR #6](https://github.com/sceneeeee/navida-habitat/pull/6) | Original suite, not rerun today |
| Model inference | Official checkpoint on RTX 4060 Ti 8 GB, 4-bit | PR #6 | Local checkpoint was called successfully |
| Memory | Approximately 3.12 GiB peak **allocated** GPU memory | PR #6 | Not total, reserved, or steady-state memory |
| Habitat smoke | One random PointNav episode; five simulator steps | PR #6 | HTTP, parser, model, action queue and Habitat steps connected; instruction not goal-aligned |
| Evaluator-side HTTP adapter | Two-step real-checkpoint integration smoke | [RtimesC/habitat-lab PR #4](https://github.com/RtimesC/habitat-lab/pull/4) | Same engineering smoke boundary, separate collaborator repository |
| Goal-grounded test-scene run | Real NaVIDA checkpoint, 80 simulator steps, STOP, success 0.0, SPL 0.0, final distance ~8.620 m | [RtimesC/habitat-lab PR #5](https://github.com/RtimesC/habitat-lab/pull/5) | A **completed but failed** single-episode navigation attempt; not a benchmark |
| Grounded demo Oracle check | Oracle success 1.0, SPL 1.0, final distance ~0.055 m | RtimesC/habitat-lab PR #5 | Confirms scene/goal/evaluation setup only; not NaVIDA results |
| Evaluator-side grounded demo tests | 54 passed, one skipped | RtimesC/habitat-lab PR #5 | Historical result in a separate repository; not rerun now |
| Logging | trajectory.csv, RGB frames and MP4 generated during historical smoke | PR #6 | Artifacts are not available in this source repository |
| Parser audit | Three parsed sub-chunks, two selected, one ignored, with atomic action metadata | PR #6 | Recorded model-output to action conversion |

**Critical distinction:** PR #6's five-step smoke test had a manual instruction **not aligned** with the random PointNav goal, so it is not a navigation task test. PR #5 in the *paired evaluator repo* did conduct an **instruction/goal-grounded 80-step run**, but **NaVIDA failed to reach the goal**. Its success/SPL values characterize only that individual engineering episode, **not an official VLN benchmark or generalization**. Oracle success must never be assigned to NaVIDA.

## Evidence provenance

- Source-code behavior was inspected through the GitHub repository, including HTTP service, policy, action parser, CLI and tests.
- Merged pull requests #1–#6 and the original Stage 2 technical record supply historical model-side validation. The RtimesC/habitat-lab PR #4 and #5 descriptions supply evaluator-side adapter and grounded-demo evidence. Attribution details: [contribution-audit.md](contribution-audit.md).
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

- A broader sample of goal/instruction-aligned autonomous episodes and detailed failure/outcome analysis beyond the **one failed 80-step grounded demo**.
- Standard R2R VLN-CE / RxR protocol, held-out scenes and comparable SR/SPL/NE aggregate benchmark metrics. The individual demo's 0.0 success/SPL does not substitute for a benchmark.
- Multi-episode performance statistics and controlled failure analysis.
- Jetson, ROS 2 or physical FrogBot deployments.
- A reproducible independent run in a newly prepared environment.

See [SURF closeout report](surf-closeout.zh-CN.md) for the final project boundary.

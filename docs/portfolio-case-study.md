# SURF Project Case Study — NaVIDA–Habitat Integration

**Project type:** Team research / robotics AI systems engineering (SURF)  
**Status:** SURF concluded; integration validated, one goal-grounded single-scene experiment completed with a negative navigation result; formal VLN benchmark not completed  
**Repository:** [sceneeeee/navida-habitat](https://github.com/sceneeeee/navida-habitat)  
**Evaluator-side integration:** [RtimesC/habitat-lab](https://github.com/RtimesC/habitat-lab)

## Problem

Visual-language navigation (VLN) research often separates the model runtime from the simulator that executes actions and evaluates trajectories. The SURF engineering task was to connect the public NaVIDA model checkpoint to Habitat, with a traceable and deliberately constrained inference protocol, while maintaining a practical GPU memory budget.

The delivered system is an **integration and evaluation interface**, not a new VLN policy, a trained model, or a physical robot controller.

## Architecture and engineering decisions

~~~text
Habitat simulator (evaluator-side repository)
     | current RGB as PNG/base64; instruction; episode/step IDs
     v
Localhost HTTP API: /v1/episodes/start -> /v1/steps
     | sequential simulator-step validation and episode state
     v
OfficialNaVIDAPolicy
     | frame history (up to 8 sampled past RGB frames + current)
     v
NaVIDA checkpoint runtime (lazy loading; local 4-bit inference)
     | raw action text, metadata and latency
     v
Strict action-chunk parser
     | first two parsed sub-chunks, bounded movement expansion
     v
Server-side atomic-action queue
     | exactly one action response per simulator step
     v
Habitat env.step / evaluator-owned trajectory and media logging
~~~

Key design choices:

- **Separated responsibilities.** The model-serving repository owns inference and action conversion; the paired Habitat-Lab repository owns simulator episodes and trajectory/evaluation artifacts.
- **Stateful but explicit.** The HTTP server tracks the active episode, expected simulator step, model decision step and queued atomic actions. A new model decision is requested only when the action queue is empty.
- **Strict output handling.** Invalid model text is reported as invalid; no random or move-forward action is silently substituted. The evaluator should terminate an invalid episode.
- **Controlled observations.** The paper_pure route receives current and historical RGB observations and the instruction, without privileged goal geometry, depth, GPS, compass or top-down map data.
- **Hardware-aware inference.** Historical validation used 4-bit inference on an RTX 4060 Ti 8 GB. This does not imply Jetson support or real-time on-robot suitability.

The parser is intentionally stricter than some behaviors of the upstream evaluator. This is **not** a byte-for-byte reproduction of the official evaluation stack.

## Delivered components

| Component | Evidence |
| --- | --- |
| Strict action parser and atomic expansion | [action_chunk.py](../src/navida_habitat/action_chunk.py) |
| Mock episode runner and JSONL logging | [episode_runner.py](../src/navida_habitat/episode_runner.py), [PR #1](https://github.com/sceneeeee/navida-habitat/pull/1) |
| Habitat-Sim RGB/action adapter | [habitat_env.py](../src/navida_habitat/habitat_env.py), [PR #2](https://github.com/sceneeeee/navida-habitat/pull/2) |
| Checkpoint runtime and RGB history | [model_runtime.py](../src/navida_habitat/model_runtime.py), [frame_history.py](../src/navida_habitat/frame_history.py), [PR #3](https://github.com/sceneeeee/navida-habitat/pull/3) |
| Policy-facing episode lifecycle | [policy.py](../src/navida_habitat/policy.py), [PR #5](https://github.com/sceneeeee/navida-habitat/pull/5) |
| Stateful HTTP inference service | [http_service.py](../src/navida_habitat/http_service.py), [PR #6](https://github.com/sceneeeee/navida-habitat/pull/6) |
| Paired evaluator-side HTTP adapter | [RtimesC/habitat-lab PR #4](https://github.com/RtimesC/habitat-lab/pull/4), authored by sceneeeee | 
| Grounded Habitat single-episode demo | [RtimesC/habitat-lab PR #5](https://github.com/RtimesC/habitat-lab/pull/5), authored by sceneeeee |

## Evidence and results

**All figures below are historical repository/PR evidence, not results remeasured for this case study.**

- **Automated regression suite:** 88 tests run; 87 passed and one optional real-scene integration test skipped (recorded in PR #6).
- **Checkpoint execution:** the actual model was loaded and called with local 4-bit inference on an RTX 4060 Ti 8 GB.
- **GPU memory:** approximately **3.12 GiB peak allocated GPU memory** in the recorded real-checkpoint smoke test. This is not peak reserved memory or full-system consumption.
- **Simulator integration:** one randomly selected PointNav test episode executed **five simulator steps** through the two-process model/HTTP/Habitat path. The recorded steps produced valid actions and trajectory/media artifacts without HTTP errors, fallback actions, invalid outputs or collisions.
- **Auditability:** model output, parser metadata, decision-step identity and queued-step reuse could be traced through the evaluator integration.
- **Grounded single-scene demo (paired repository PR #5):** a deterministic test-scene episode with a goal-linked instruction was executed for **80 simulator steps** using the real checkpoint; the model stopped at the wrong location (**NaVIDA success=0.0, SPL=0.0, final goal distance ~8.620 m**). A separate Oracle control completed the episode (success=1.0, SPL=1.0); this validates the goal/scene/evaluator setup, **not NaVIDA performance**. The PR reports 54 tests passed, one skipped and genuine trajectory/media outputs.

**Evidence distinction:** the five-step smoke test used a manually supplied instruction **not aligned** with its random PointNav goal, so it only establishes engineering connectivity. The later **80-step grounded demo did use a goal-linked instruction**, but NaVIDA **failed the task**. Neither observation is a formal R2R/RxR benchmark or a generalization estimate.

See [the validation report](validation-report.md) and [PR #6](https://github.com/sceneeeee/navida-habitat/pull/6) for evidence boundaries.

## Contribution attribution

All 17 historical main-branch commits in this repository were authored as **evenS**, linked to GitHub **sceneeeee**, and all model-side [PRs #1–#6](https://github.com/sceneeeee/navida-habitat/pulls?q=is%3Apr+is%3Amerged) were submitted from that account. In the separate RtimesC team evaluator repository, the same account also authored [PR #4 (HTTP adapter)](https://github.com/RtimesC/habitat-lab/pull/4) and [PR #5 (grounded demo)](https://github.com/RtimesC/habitat-lab/pull/5). Thus, the evidence supports responsibility for these specific model-side and evaluator-side integration deliverables. It **does not** prove that every line was manually typed or that all surrounding Habitat evaluator code was written by the same person. Other team contributions remain separate. See the [commit-by-commit attribution audit](contribution-audit.md).

Do not attribute upstream NaVIDA model design, training, public checkpoint or the Habitat frameworks to this repository's author.

## Scope and limitations

- One goal-grounded single-scene engineering episode was completed but failed; SURF ended without a standardized instruction-aligned VLN benchmark or a successful navigation result in the documented grounded run.
- No official R2R VLN-CE or RxR benchmark result is documented here.
- No FrogBot, ROS 2, Jetson or other physical-robot deployment is claimed.
- The service is intended for localhost research integration, not hardened production use.
- The model, datasets, scenes and recorded videos are not distributed with this repository.
- License permissions must be checked separately for the model, upstream code, third-party simulation frameworks and this repository; no root repository LICENSE has been selected.

## Post-SURF personal repository consolidation (2026-11)

After the SURF project concluded, the personal repository extracted the relevant evaluator application and original tests from the [July 23 merged team snapshot](https://github.com/RtimesC/habitat-lab/tree/835ac41e9ecf82c2c13b4bdf2f6747aef70860d6). The aim is **independent maintainability and credible portfolio demonstration**, not retroactively treating team framework code as individual SURF authorship. The extracted model/evaluator code now lives in one source repository but still runs as **two separately configured Python processes**. Source file hashes were checked after import; post-migration Habitat/GPU tests are **not yet run**. Attribution, licensing and acceptance gates are recorded in [evaluator provenance](evaluator-provenance.md) and [migration acceptance checklist](evaluator-migration-acceptance.md).

## Reproducibility and further work

Standard-library regression command (requires dependencies already present):

~~~bash
PYTHONPATH=src python -m unittest discover -s tests -v
~~~

The full model/Habitat test additionally requires properly licensed scenes, model checkpoint, CUDA runtime and the paired evaluator. Running the command above does **not** reproduce the five-step real-model experiment.

Post-SURF simulation evaluation or an authorized future FrogBot experiment would be **new work** and should be reported separately from the completed SURF deliverable.

## Suggested résumé wording

> Built and validated the model-side NaVIDA–Habitat integration and authored the paired evaluator-side HTTP adapter and grounded simulation demo; implemented 4-bit inference, RGB history, strict action parsing and a stateful action queue. Demonstrated a five-step connectivity smoke test and diagnosed an 80-step goal-grounded run where NaVIDA stopped at the wrong location (success=0), with clear separation from official VLN benchmark claims.

This wording is supported by account-linked merged PRs; review team work division and any AI-assisted development details before claiming exclusively hand-written implementation.

# SURF Project Case Study — NaVIDA–Habitat Integration

**Project type:** Team research / robotics AI systems engineering (SURF)  
**Status:** SURF concluded; engineering integration validated in simulation; formal navigation evaluation not completed  
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

## Evidence and results

**All figures below are historical repository/PR evidence, not results remeasured for this case study.**

- **Automated regression suite:** 88 tests run; 87 passed and one optional real-scene integration test skipped (recorded in PR #6).
- **Checkpoint execution:** the actual model was loaded and called with local 4-bit inference on an RTX 4060 Ti 8 GB.
- **GPU memory:** approximately **3.12 GiB peak allocated GPU memory** in the recorded real-checkpoint smoke test. This is not peak reserved memory or full-system consumption.
- **Simulator integration:** one randomly selected PointNav test episode executed **five simulator steps** through the two-process model/HTTP/Habitat path. The recorded steps produced valid actions and trajectory/media artifacts without HTTP errors, fallback actions, invalid outputs or collisions.
- **Auditability:** model output, parser metadata, decision-step identity and queued-step reuse could be traced through the evaluator integration.

**What these results do not show:** the manual navigation instruction was not aligned with the PointNav task goal. The five-step smoke test therefore demonstrates **engineering connectivity**, not language-grounded target completion, official Success Rate (SR), Success weighted by Path Length (SPL), or generalization.

See [the validation report](validation-report.md) and [PR #6](https://github.com/sceneeeee/navida-habitat/pull/6) for evidence boundaries.

## Contribution attribution

The GitHub record contains merged contributions under the sceneeeee account in [PRs #1–#6](https://github.com/sceneeeee/navida-habitat/pulls?q=is%3Apr+is%3Amerged). The repository-level work covers the integration components above. **Individual authorship, supervisor/team contribution and the division of work across the paired evaluator repository should be verified against the SURF team's records before using first-person ownership statements in a CV or graduate application.**

Do not attribute upstream NaVIDA model design, training, public checkpoint or the Habitat frameworks to this repository's author.

## Scope and limitations

- SURF ended before a standardized, instruction-aligned VLN evaluation was produced.
- No official R2R VLN-CE or RxR benchmark result is documented here.
- No FrogBot, ROS 2, Jetson or other physical-robot deployment is claimed.
- The service is intended for localhost research integration, not hardened production use.
- The model, datasets, scenes and recorded videos are not distributed with this repository.
- License permissions must be checked separately for the model, upstream code, third-party simulation frameworks and this repository; no root repository LICENSE has been selected.

## Reproducibility and further work

Standard-library regression command (requires dependencies already present):

~~~bash
PYTHONPATH=src python -m unittest discover -s tests -v
~~~

The full model/Habitat test additionally requires properly licensed scenes, model checkpoint, CUDA runtime and the paired evaluator. Running the command above does **not** reproduce the five-step real-model experiment.

Post-SURF simulation evaluation or an authorized future FrogBot experiment would be **new work** and should be reported separately from the completed SURF deliverable.

## Suggested résumé wording

> Developed a stateful NaVIDA–Habitat inference integration during a SURF research project, connecting 4-bit checkpoint inference, RGB frame history, strict action parsing and a localhost HTTP action queue; validated the model-to-simulator path with a five-step real-checkpoint smoke test and historical regression tests (87 passed, one optional integration test skipped).

Use this only after confirming that the described engineering work matches your actual individual role within the SURF team.

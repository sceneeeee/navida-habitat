# Final engineering closeout — NaVIDA–Habitat

**Project status: COMPLETED — software integration and deterministic Habitat engineering showcase.**
**SURF research period:** concluded.
**Personal repository consolidation:** merged into `main` through PR #8 on 2026-11-15.
**Final engineering evidence:** [engineering-demo.md](engineering-demo.md).

This document supersedes the earlier migration checklist and its interim status notes. Earlier sections in the SURF closeout, validation report and provenance history remain historical records and should be read with their original dates.

## 1. Final scope

The completed deliverable is a maintainable repository containing:

- NaVIDA-side model runtime, RGB history, strict action parsing, episode state and HTTP inference service.
- Extracted SURF Habitat evaluator application, HTTP client, navigation runner, action execution, trajectory/media recording and relevant tests.
- Two explicitly separate runtime environments: Python 3.10 model/service and Python 3.9 Habitat evaluator (Habitat-Lab/Sim 0.3.3).
- Reproducible deterministic Fake Policy engineering demo, tests, bilingual README, source provenance and selected small presentation assets.

The project is **not** a successful learned-navigation result, official VLN benchmark reproduction, production service or physical-robot deployment. This does **not** mean the original model was never run: the official NaVIDA-3B checkpoint was loaded and exercised during SURF, as recorded in [PR #6](https://github.com/sceneeeee/navida-habitat/pull/6) and [team evaluator PR #5](https://github.com/RtimesC/habitat-lab/pull/5).

## 2. Completed acceptance gates

| Gate | Final evidence | Status |
|---|---|---|
| Historical source integrity | 35 imported files matched the frozen SURF source snapshot by Git blob SHA at initial import; subsequent changes are listed in the manifest/provenance | Passed |
| Historical real-checkpoint integration | Official NaVIDA-3B loaded with 4-bit NF4 on RTX 4060 Ti 8GB; ≈3.12 GiB peak allocated VRAM; five-step real-model Habitat/HTTP smoke recorded in personal PR #6 | Passed as integration smoke |
| Historical goal-grounded model run | Real checkpoint executed 80 steps in team Habitat PR #5; stopped at wrong location, success=0, SPL=0, final distance ≈8.620 m | Completed; navigation unsuccessful |
| License and attribution | Original Habitat-Lab MIT notice preserved; team framework and account-linked PR #4/#5 contributions distinguished | Passed |
| Python 3.10 model-side suite | 98 passed, 1 skipped, 0 failed in the final showcase run | Passed |
| Python 3.9 evaluator-side suite | 56 passed, 0 failed in the final showcase run | Passed |
| Habitat runtime | Real Habitat-Lab/Sim 0.3.3, skokloster-castle scene/navmesh, WSLg D3D12 rendering and reset | Passed |
| Motion semantics | Forward 0.249999864 m; left/right turns approximately 15 degrees; two left turns approximately 30 degrees; STOP ended episode | Passed |
| HTTP client/server | Real localhost TCP, RGB PNG transport, episode/step ordering, action queue and decision-step reuse | Passed |
| Normal/invalid execution | Normal case: 4 requests/4 Env steps; invalid case: 3 requests/2 Env steps, explicit invalid-output failure and no replacement action | Passed |
| Runner artifacts | Real Habitat RGB, CSV/JSON summaries, terminal pose, H.264 videos and cleanup checks | Passed |
| Curated showcase | One fixed-start 640x480 Fake Policy run: 21 actions, 21 requests, 11 fixed decisions, 0 collisions, explicit STOP; 10.5-second H.264 clip | Passed |
| GitHub CI | Lightweight HTTP/config/demo regression workflow passed on the merged PR head | Passed |

Exact commands, environment details and artifact semantics are documented in [engineering-demo.md](engineering-demo.md). CI uses fakes and compile checks; it does not launch Habitat, load model weights or reproduce the local simulation.

## 3. Explicitly out of scope / not completed

These items are **not merge blockers** for the completed software-integration project and must not be represented as completed achievements:

- Replaying the NaVIDA checkpoint in the consolidated personal repository after migration. The historical SURF checkpoint run did happen; only a fresh post-migration replay was not performed.
- Successful language-grounded navigation. The historical 80-step NaVIDA episode stopped at the wrong location (success=0, SPL=0, final distance about 8.620 m); the separate Oracle result is not NaVIDA performance.
- Standard R2R VLN-CE / RxR benchmark, held-out multi-scene evaluation or aggregate SR/SPL/NE/nDTW claims.
- Jetson, ROS 2, FrogBot or other physical-robot deployment.
- Production hardening of the localhost HTTP service.
- Cross-platform rendering and semantic-scene annotation validation.

A future real-checkpoint replay or research experiment is optional follow-up work and should be recorded separately, not used to reopen this completed SURF engineering deliverable.

## 4. Reproduction

See [the engineering demo guide](engineering-demo.md). The repository contains the bounded demo runner and exporter; it does not install packages or download model weights, scenes or datasets automatically.

Use the matching Python environments and authorized Habitat test assets. Replace local interpreter and scene paths with paths on the target machine. Do not install the Python 3.10 root package into the Python 3.9 evaluator environment.

## 5. Repository hygiene and licensing

- The selected, labelled 640x480 presentation clip and small evidence derivatives are intentionally versioned under `docs/assets/`.
- Large raw recordings, full-resolution run directories, model weights, GLB/navmesh scenes, datasets, credentials and local `temp_report.md` remain untracked/ignored.
- The original Habitat-Lab MIT notice is retained at [third_party/habitat-lab-MIT.LICENSE](../third_party/habitat-lab-MIT.LICENSE).
- **No repository-wide license has been selected for the personal model-side code.** The preserved third-party MIT notice does not automatically license every file in this repository. This is a deliberate unresolved owner decision, not a failed engineering gate.

## 6. Final disposition

The SURF / NaVIDA–Habitat software integration and its deterministic real-Habitat engineering showcase are **closed and complete**. No further implementation is required for this project’s stated engineering scope.

Keep the repository public and maintainable as a completed portfolio project. Do not archive it merely because the project is complete; archive only if the owner later decides to stop accepting maintenance changes.
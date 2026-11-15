# Git history contribution audit — SURF NaVIDA–Habitat

**Audit date:** 2026-11-07. **Evidence basis:** GitHub PR authorship, commit author metadata, changed-file lists and the original PR validation descriptions; not an interview with teammates or a manual-code authorship investigation.

## Clarification from the repository owner (2026-11-07)

The owner confirms that the personal **sceneeeee/navida-habitat** model-side repository was developed and maintained by the owner with **Codex assistance**, and did not involve another human collaborator. This first-person statement is consistent with, but not proved solely by, its Git history. The **RtimesC/habitat-lab** evaluator is nevertheless a separate **SURF team repository**; only the specific changes documented below are account-attributable, and its broader base framework has its own contributors.

## What the history supports

In the default branch of [sceneeeee/navida-habitat](https://github.com/sceneeeee/navida-habitat), the 17 commits available before this closeout branch (initial scaffold through July 23) all have Git author **evenS**, linked to GitHub account **sceneeeee**. Its six historical PRs (#1–#6) were opened by sceneeeee, and their individual PR commit lists contain only evenS / sceneeeee as author. No Co-authored-by footer was found in these PR commit messages.

This provides **strong Git attribution** for responsibility for the integration and delivery of these repository changes. It does **not** independently prove all lines were manually typed by the account owner, that no teammates reviewed or helped, or that no AI coding assistance was used.

### Model-side repository — sceneeeee/navida-habitat

| PR | Account-linked evidence | Concrete changes |
| --- | --- | --- |
| [#1](https://github.com/sceneeeee/navida-habitat/pull/1) | sceneeeee / evenS | Deterministic mock backend/environment, bounded episode runner, JSONL logs and regression tests |
| [#2](https://github.com/sceneeeee/navida-habitat/pull/2) | sceneeeee / evenS | Habitat-Sim environment adapter, RGB/atomic action interface, GLX/WSLg setup notes, tests |
| [#3](https://github.com/sceneeeee/navida-habitat/pull/3) | sceneeeee / evenS | Official checkpoint runtime, 4-bit local resource adaptation, frame history, multi-decision Habitat runner |
| [#4](https://github.com/sceneeeee/navida-habitat/pull/4) | sceneeeee / evenS | Stage 3 README, technical and run documentation |
| [#5](https://github.com/sceneeeee/navida-habitat/pull/5) | sceneeeee / evenS | Evaluator-facing Policy API: reset/observe/act lifecycle, decision metadata and tests |
| [#6](https://github.com/sceneeeee/navida-habitat/pull/6) | sceneeeee / evenS | Local HTTP server, episode state, atomic-action queue, request validation, tests and audit metadata |

### Evaluator-side collaboration — RtimesC/habitat-lab

The evaluator framework and much of the surrounding work belong to the **RtimesC team repository**, not automatically to sceneeeee. However, the following PRs in that repository are also authored by **sceneeeee**, with their PR commits authored by **evenS**:

| PR | Evidence-backed personal account contribution | Validation boundary |
| --- | --- | --- |
| [RtimesC/habitat-lab #4](https://github.com/RtimesC/habitat-lab/pull/4), merged July 22 | Habitat-side HTTP client adapter, strict paper_pure action bypass, RGB PNG/base64 request handling, step/episode integration, WSLg renderer override and related tests | Real model **two-step** integration smoke; instruction did not match the random PointNav goal |
| [RtimesC/habitat-lab #5](https://github.com/RtimesC/habitat-lab/pull/5), merged July 23 | Grounded deterministic single-episode dataset generator, demo CLI, loading instruction from episode metadata, evaluator/recorder/artifact handling, regression tests | **80-step real-checkpoint grounded test**, NaVIDA stopped at wrong location; no standard benchmark |

PR #5 reports a historical *single-scene engineering experiment*: the Oracle validated episode setup (success 1.0 / SPL 1.0), whereas **NaVIDA success = 0.0, SPL = 0.0**, final goal distance about **8.620 m** after 80 steps, with a normal STOP. These are *different policies*; Oracle success must not be presented as NaVIDA success. The PR reports 54 tests passed, one skipped, and generated 80 RGB frames, CSV, JSON/Markdown summary and MP4. These were not rerun in this audit, and are not standard R2R/RxR/MP3D/HM3D benchmark scores.

Another [RtimesC/habitat-lab PR #10](https://github.com/RtimesC/habitat-lab/pull/10), authored by sceneeeee and merged on September 14, implements a later reactive DoorNav baseline. **Do not automatically attribute this later work to the completed SURF NaVIDA delivery** without evidence that it was part of the original SURF scope.

## Recommended role statement

**Conservative and evidence-backed:**
“Responsible for the model-side NaVIDA–Habitat engineering integration and authored the paired evaluator-side HTTP adapter and grounded single-episode demo, with an auditable Python test and simulation workflow.”

**In a technical interview:** be ready to explain how the server's episode/decision/atomic-action state relates to Habitat steps, why the parser uses no fallback, and the contrast between a successful integration smoke test and the grounded experiment in which NaVIDA failed.

## What not to claim

- Independently designed or trained the original NaVIDA model.
- Authored the entire Habitat-Lab evaluator framework or all team work.
- Personally hand-wrote every line of code solely on the basis of Git metadata.
- Achieved positive NaVIDA task success in the grounded run.
- Completed a formal R2R VLN-CE benchmark, Jetson deployment or physical FrogBot validation.

The Git record establishes **account-level software contribution**. The precise personal/team/AI-assistance workflow can be explained transparently without diminishing engineering design, integration, debugging and validation responsibilities.

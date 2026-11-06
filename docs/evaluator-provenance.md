# SURF evaluator code provenance and reuse

**Migration snapshot:** [RtimesC/habitat-lab @ 835ac41e](https://github.com/RtimesC/habitat-lab/tree/835ac41e9ecf82c2c13b4bdf2f6747aef70860d6) — merged [PR #5](https://github.com/RtimesC/habitat-lab/pull/5) on 2026-07-23.

## Why this repository includes an extracted evaluator application

The SURF research project used two GitHub repositories:

- `sceneeeee/navida-habitat`: model runtime, RGB frame history, strict action chunk parsing, server state/action queue, and localhost HTTP API.
- `RtimesC/habitat-lab`: the full team's fork of Meta Habitat-Lab plus its custom `habitat_vln` application and evaluator-side scripts.

For an independently maintainable engineering portfolio, this repository carries an **extracted, historical subset of the SURF custom evaluator layer** under `habitat_vln/` and its relevant historical tests under `test/`. It does **not** incorporate Meta's complete Habitat-Lab source distribution, team-owned Git history, dataset files, checkpoints or simulation media. The external Habitat-Lab and Habitat-Sim installations remain required dependencies.

The extracted source files were originally located at **the same relative paths** in the historical RtimesC/habitat-lab commit referenced above. The migration preserves the historical code for auditability; new modifications must be distinguished from those upstream files.

## Authorship and credit

**Recorded account-linked contributions by sceneeeee / evenS:**

- [RtimesC/habitat-lab PR #4](https://github.com/RtimesC/habitat-lab/pull/4): evaluator-facing `OfficialNaVIDAHTTPPolicy`, environment/runner integration, PNG/base64 transport, strict no-fallback behavior, WSLg renderer option, and tests.
- [RtimesC/habitat-lab PR #5](https://github.com/RtimesC/habitat-lab/pull/5): goal-grounded test-scene episode generator, demo runner, trajectory/media handling, and tests.

**Code incorporated from RtimesC's wider application framework** — such as the common `NavigationRunner`, simulation environment wrappers, controller, scheduler, recorder and generalized policy abstractions — may include contributions from other team members. The single commit that imports a file into this repository does **not** reassign its original authorship to the personal repository owner. See the original [commit history](https://github.com/RtimesC/habitat-lab/commits/835ac41e9ecf82c2c13b4bdf2f6747aef70860d6/habitat_vln) and [local contribution audit](contribution-audit.md) for boundaries.

**Framework attribution:** Meta's Habitat-Lab and Habitat-Sim are separate upstream projects. The RtimesC/habitat-lab codebase includes a root MIT license carrying Meta Platforms copyright. The license text is preserved verbatim in [third_party/habitat-lab-MIT.LICENSE](../third_party/habitat-lab-MIT.LICENSE). Any use of model weights, scenes or datasets is subject to their independent terms and access controls.

## Explicit boundaries

- The snapshot is not a claim that the original SURF repository, team or Meta code is wholly authored by sceneeeee.
- Do not report the original **Oracle** success as NaVIDA success. PR #5's single grounded test produced NaVIDA **success=0.0**, **SPL=0.0**, about **8.620m final goal distance**, after 80 steps.
- Post-July DoorNav B1 work (RtimesC/habitat-lab PR #10) and unrelated team robot branches are not included in this migration.
- Training/QLoRA experimental scripts are not migrated and no model weights or datasets are bundled.
- This import was **not revalidated** under the personal repository's file layout; a GPU/Habitat replay remains a separate acceptance task.

## Minimal maintenance rule

The two processes intentionally retain different Python environments: model server **Python 3.10**; historical Habitat evaluator **Python 3.9**. The HTTP API is the integration seam. Avoid forcing a single Python environment by changing production dependencies without explicit compatibility tests.

When source files are changed, preserve license/attribution and document where changes occur after the historical snapshot.

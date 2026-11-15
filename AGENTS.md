# Repository instructions — SURF NaVIDA–Habitat consolidation

## Project scope

- Model/server side: src/navida_habitat/, scripts/, tests/; Python 3.10.
- Extracted evaluator side: habitat_vln/, test/; original SURF Habitat-Lab Python 3.9 environment.
- The two sides communicate over localhost JSON/PNG HTTP; do not merge their Python requirements without separate compatibility evidence.
- The evaluator package derives from RtimesC/habitat-lab snapshot 835ac41e (2026-07-23); preserve its MIT license and the contributor/provenance record in docs/evaluator-provenance.md.
- Do not copy official NaVIDA model source code, pretrained model weights, licensed scenes, datasets or unrelated team/Meta Habitat-Lab code.

## Protocol and scientific integrity

- paper_pure model inputs: current RGB, bounded previous RGB and navigation instruction. No privileged target distance/bearing, simulator poses, GPS, compass, depth or top-down goal maps in policy inputs.
- Strict action chunk parser, no random or move-forward fallback, no goal-distance force-stop, anti-stuck override or hidden oracle control in paper_pure.
- Differing upstream behaviors must be disclosed, not portrayed as identical official reproduction.
- A five-step unaligned model/Habitat smoke is not task success.
- The historical 80-step grounded single-episode NaVIDA run ended at the wrong location (success=0); separate Oracle success must never be credited to NaVIDA.
- Do not fabricate benchmark results, passed tests, media or measured GPU utilization.

## Development and testing

1. Inspect git status, current branch, original relevant PRs and imported dependencies before editing.
2. Keep model/server changes separated from evaluator-specific changes; avoid unrelated refactors.
3. Do not modify external team repositories.
4. Do not install heavy dependencies, download checkpoints or scenes, retrain, or launch long GPU simulations without explicit direction.
5. Check source/test compatibility in the correct Python environment.
6. Model-side test (Python 3.10): PYTHONPATH=src python -m unittest discover -s tests -v
7. Evaluator-side tests (Python 3.9 with Habitat dependencies): python -m unittest discover -s test -p 'test_grounded_demo_episode.py' -v and other relevant targeted patterns.
8. Verify source file provenance and document differences from original PR #5 snapshot.

## MANDATORY Codex session handoff

At the **end of every Codex run**, including failed or partially completed runs, create or append a dated section to the repository-root **temp_report.md**. Include:

- current date and UTC/local time if known
- current branch and HEAD; git status and preexisting changes
- user goal and completed or pending phases
- changed and inspected files
- test commands actually run and exact pass/fail/skip counts
- commands not run, missing dependencies and environment blockers
- critical technical decisions, pitfalls, license/provenance caveats
- recommended next steps and how a fresh Codex chat should continue

**Never commit or push temp_report.md**; it is ignored by the project .gitignore. Verify with git status --ignored and git diff --cached --name-only before any explicitly requested commit. Do not force-add it. Append rather than overwrite useful history.

Do not create Git commits, push, merge branches, publish releases or alter other repositories unless explicitly requested.

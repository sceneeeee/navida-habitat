# SURF evaluator migration acceptance checklist

**Source frozen:** RtimesC/habitat-lab merge of PR #5 at `835ac41e9ecf82c2c13b4bdf2f6747aef70860d6`.

The GitHub migration imports **35** historical `habitat_vln/` application and selected `test/` source/test files (258,210 bytes), all verified by exact matching Git blob hashes against the historical source snapshot. No GPU or Habitat execution happened in the remote GitHub editing environment. The initial GitHub-only import did not run the fake-policy HTTP test. Local post-import checks are recorded below.

## Acceptance gates

1. Verify the imported relative paths and file content against the historical source snapshot.
2. Verify original MIT notice is retained and the source/author attribution is explicit.
3. Run Python 3.10 model-side tests separately from Python 3.9 evaluator-side tests.
4. Confirm the external Habitat-Lab/Habitat-Sim versions and the PointNav config path; document the exact environment in `temp_report.md`.
5. Run evaluator tests with scene-independent fakes first; record passed/skipped/failed counts.
6. Perform GET /health, episode reset, one image step through the actual HTTP server; check error/no-fallback paths.
7. With licensed test scene and checkpoint, run the grounded demo and collect episode JSON, trajectory CSV, RGB frames and MP4. Check actual results and logs, including failure cases, without altering the frozen historical evidence.
8. Compare claimed model success with the evaluator result; the historical 80-step run **failed**, and Oracle was separate.
9. Review README against the actual post-migration runtime; only then mark this personal repo's evaluator as verified.
10. Verify no checkpoints, datasets, generated results/videos, access secrets or `temp_report.md` are included in git commits.

**Implementation note:** downstream code historically depends on `habitat` imports and Python 3.9; source was copied verbatim at import. Post-import changes are explicitly listed in evaluator-provenance.md and the manifest; the original hashes remain an audit baseline.


## Local checks after import (2026-11-12)

Python 3.10 configuration/CLI unit tests use explicit fake Habitat boundaries;
they do not validate a Python 3.9 Habitat installation or measure movement.
The real localhost server/client contract uses an injected fake policy, without
checkpoint or simulator. See `temp_report.md` (local, ignored) for exact commands
and counts. Neither check closes gates 4 or 7.

Before scene replay, inspect the resolved Habitat config and verify Official
HTTP mode has `forward_step_size=0.25`, `turn_angle=15`. Measure motion in the
real simulator as a separate check. Ordinary/Oracle policies retain their
original geometry. Compare current files against the manifest's original
hashes using its downstream exception list rather than expecting all 35 hashes
to remain identical after fixes.

Deferred artifact follow-ups: CSV pose/image are before the action while
metrics are after it; document pre/post fields and add a terminal pose/frame in
a separate schema change. For video failures, minimally add an error when
`write_video` returns False, then test that summary branch with the real runner.
Neither issue is fixed by the configuration tests.

Actual local result: `/usr/bin/python3.10` full `tests/` suite ran 97 tests:
96 passed, 1 opt-in real-scene test skipped, 0 failures/errors after localhost
socket permission was granted. The 8 new configuration tests and 1 existing
HTTP contract test passed within that suite. `compileall` and `git diff --check`
passed. No real Habitat or checkpoint was run; Python 3.9 remains unavailable.

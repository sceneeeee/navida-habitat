# SURF evaluator migration acceptance checklist

**Source frozen:** RtimesC/habitat-lab merge of PR #5 at `835ac41e9ecf82c2c13b4bdf2f6747aef70860d6`.

The GitHub migration imports **35** historical `habitat_vln/` application and selected `test/` source/test files (258,210 bytes), all verified by exact matching Git blob hashes against the historical source snapshot. No GPU or Habitat execution happened in the remote GitHub editing environment. The new fake-policy cross-repository HTTP contract test is **not yet run**; do not claim its success until executed.

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

**Implementation note:** downstream code historically depends on `habitat` imports and Python 3.9; source copied verbatim to preserve provenance. A future compatibility refactor should be a separate tested PR, not silently folded into the SURF historical import.

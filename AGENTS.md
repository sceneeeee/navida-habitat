# Repository Instructions

- Use Python 3.10 and a `src/` package layout.
- Implement against public NaVIDA behavior; do not copy official NaVIDA source code.
- Never read or generate privileged geometry such as `target_distance`, `target_bearing`, simulator ground-truth poses, depth, GPS, compass, or top-down maps.
- In `paper_pure`, do not use Advisor, Geometric Controller, anti-stuck logic, force-stop logic, or random-action/move-forward fallbacks.
- Do not commit datasets, model weights, adapters, logs, results, or videos.
- Run the corresponding tests after every change; run the full acceptance suite before handoff.
- Unless explicitly requested, do not download models, install Habitat or other dependencies, modify files outside this repository, or create Git commits.

Run the standard-library tests with:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

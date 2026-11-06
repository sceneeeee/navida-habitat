# SURF demonstration recording checklist

This is an **optional future public recording plan**, not evidence that a new video has been published. The historical [RtimesC/habitat-lab PR #5](https://github.com/RtimesC/habitat-lab/pull/5) records an 80-step goal-grounded NaVIDA run and locally generated RGB frames, trajectory and MP4, but these media are not distributed in this repository. That run failed navigation (NaVIDA success=0), so any clip must display the negative result accurately.

For a 60–90-second video: show server start and GET /health; a legitimate licensed Habitat scene; actual RGB input and instruction; model inference and raw action output; strict parsing metadata; queued atomic actions; corresponding env.step movement; and the evaluator's real trajectory/frame/video output.

If the instruction is not grounded to the scene goal, label the clip **engineering smoke test**. Never call it a successful VLN task or benchmark. Show execution environment, run date and step count.

Before sharing: verify SURF/team permission, authorized model/scene licenses, private path and token redaction, video provenance, and contributor attribution. Do not commit videos/model weights/datasets to the repository, per AGENTS.md.

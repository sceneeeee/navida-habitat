# Local HTTP interface — implementation-based contract

Source: [http_service.py](../src/navida_habitat/http_service.py), [tests](../tests/test_http_service.py). Designed for localhost research integration, not public internet service.

## Endpoints

| Method | Route | Body | Response |
| --- | --- | --- | --- |
| GET | /health | None | {"status":"ok","policy":"official_navida","protocol":"paper_pure"} |
| POST | /v1/episodes/start | JSON with exactly "episode_id" (nonblank string) | {"episode_id":"...","reset":true} |
| POST | /v1/steps | JSON with exactly "episode_id", "simulator_step", "instruction", "rgb_png_base64" | one atomic action plus decision metadata |

The RGB field must be base64 of a **PNG with RGB mode**, not JPEG or RGBA. The server validates the request field set exactly; privileged target information is not allowed as extra fields.

### Starting the localhost server

~~~bash
export PYTHONPATH="$PWD/src"
python scripts/run_official_navida_http_server.py --model-path /path/to/licensed/checkpoint --host 127.0.0.1 --port 8008
curl -fsS http://127.0.0.1:8008/health
curl -sS http://127.0.0.1:8008/v1/episodes/start -H 'Content-Type: application/json' -d '{"episode_id":"demo-001"}'
~~~

The health endpoint does **not** trigger model checkpoint loading; runtime loading is lazy. Steps require a real image and a model/dependency setup.

### Step request example (illustrative only)

~~~json
{
  "episode_id": "demo-001",
  "simulator_step": 0,
  "instruction": "Walk toward the doorway.",
  "rgb_png_base64": "<actual base64 of RGB PNG>"
}
~~~

The placeholder above is *not* a valid runnable RGB payload.

### Step response fields

The source returns: episode_id, simulator_step, decision_step, action, valid, inferred, raw_output, error, termination_reason, latency_seconds, and metadata. Action is one of move_forward, turn_left, turn_right, stop, or null for invalid model output.

The server supports one active episode. Starting an episode resets policy state, the expected simulator step, model decision counter, frame history and action queue, but not the already loaded model. Each step must be sequential from 0; queued atomic actions are returned without another model call, and inference occurs when the queue is empty. Each response includes the originating model decision number.

On invalid model text, the service reports valid=false, action=null, termination_reason=invalid_model_output; **the evaluator, not this HTTP handler, is responsible for terminating the episode**. There are no random-action fallbacks.

## Errors

JSON error responses include: 400 malformed inputs, 404 route not found, 405 invalid HTTP method, 409 missing/wrong episode or invalid step order, 411 missing Content-Length, 413 oversized request (8 MiB default), 415 wrong Content-Type, 500 internal error.

The parser accepts one to three sub-chunks; only the first two are executed. Forward and turn actions use 25 cm and 15-degree atomic steps, respectively. Strict parsing/no fallback differs from parts of the upstream evaluator; avoid describing it as an identical official reproduction.

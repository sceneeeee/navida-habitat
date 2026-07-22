"""Local HTTP service for the evaluator-facing Official NaVIDA policy."""

from __future__ import annotations

import base64
import binascii
import io
import json
import threading
from collections import deque
from dataclasses import dataclass
from enum import Enum
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from PIL import Image, UnidentifiedImageError

_ALLOWED_ACTIONS = frozenset(
    {"move_forward", "turn_left", "turn_right", "stop"}
)
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8008
DEFAULT_MAX_REQUEST_BYTES = 8 * 1024 * 1024


class ProtocolError(Exception):
    """A request error that can be reported safely to an HTTP client."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class _DecisionResponseState:
    decision_step: int
    raw_output: str
    valid: bool
    error: str | None
    latency_seconds: float
    metadata: dict[str, object]


class OfficialNaVIDAHTTPService:
    """Own evaluator protocol state independently of the HTTP transport."""

    def __init__(self, *, policy: Any) -> None:
        self._policy = policy
        self._lock = threading.Lock()
        self._episode_id: str | None = None
        self._expected_simulator_step = 0
        self._model_decision_step = 0
        self._action_queue: deque[str] = deque()
        self._queued_decision: _DecisionResponseState | None = None
        self._closed = False

    def health(self) -> dict[str, object]:
        """Return a readiness response without touching the model policy."""

        return {
            "status": "ok",
            "policy": "official_navida",
            "protocol": "paper_pure",
        }

    def start_episode(self, payload: object) -> dict[str, object]:
        """Reset policy and service state for one evaluator episode."""

        request = self._require_exact_fields(payload, {"episode_id"})
        episode_id = request["episode_id"]
        if not isinstance(episode_id, str) or not episode_id.strip():
            raise ProtocolError("episode_id must be a non-empty string")

        with self._lock:
            self._require_open()
            self._policy.reset(episode_id)
            self._episode_id = episode_id
            self._expected_simulator_step = 0
            self._model_decision_step = 0
            self._action_queue.clear()
            self._queued_decision = None

        return {"episode_id": episode_id, "reset": True}

    def process_step(self, payload: object) -> dict[str, object]:
        """Validate and process one sequential evaluator simulator step."""

        request = self._require_exact_fields(
            payload,
            {
                "episode_id",
                "simulator_step",
                "instruction",
                "rgb_png_base64",
            },
        )

        with self._lock:
            self._require_open()
            self._validate_step_request(request)
            rgb = self._decode_rgb_png(request["rgb_png_base64"])
            self._policy.observe(rgb)

            inferred = not self._action_queue
            if inferred:
                decision = self._policy.act(
                    instruction=request["instruction"],
                    decision_step=self._model_decision_step,
                )
                self._model_decision_step += 1
                decision_state = _DecisionResponseState(
                    decision_step=decision.decision_step,
                    raw_output=decision.raw_output,
                    valid=decision.valid,
                    error=decision.error,
                    latency_seconds=decision.latency_seconds,
                    metadata=dict(decision.metadata),
                )
                actions: tuple[str, ...] = ()
                if decision.valid:
                    actions = tuple(
                        self._action_value(action)
                        for action in decision.atomic_actions
                    )
                    if not actions:
                        raise RuntimeError(
                            "valid policy decision contained no atomic actions"
                        )
                self._queued_decision = decision_state
                self._action_queue.extend(actions)
            else:
                decision_state = self._queued_decision

            if decision_state is None:
                raise RuntimeError("queued action has no originating decision")

            action = self._action_queue.popleft() if self._action_queue else None
            response = {
                "episode_id": self._episode_id,
                "simulator_step": request["simulator_step"],
                "decision_step": decision_state.decision_step,
                "action": action,
                "valid": decision_state.valid,
                "inferred": inferred,
                "raw_output": decision_state.raw_output,
                "error": decision_state.error,
                "termination_reason": (
                    None
                    if decision_state.valid
                    else "invalid_model_output"
                ),
                "latency_seconds": decision_state.latency_seconds,
                "metadata": dict(decision_state.metadata),
            }
            self._expected_simulator_step += 1
            return response

    def close(self) -> None:
        """Close the owned policy exactly once."""

        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._policy.close()

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("service is closed")

    @staticmethod
    def _require_exact_fields(
        payload: object,
        expected_fields: set[str],
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ProtocolError("request JSON must be an object")
        actual_fields = set(payload)
        if actual_fields != expected_fields:
            missing = sorted(expected_fields - actual_fields)
            unexpected = sorted(actual_fields - expected_fields)
            details = []
            if missing:
                details.append(f"missing fields: {', '.join(missing)}")
            if unexpected:
                details.append(f"unexpected fields: {', '.join(unexpected)}")
            raise ProtocolError("invalid request fields; " + "; ".join(details))
        return payload

    def _validate_step_request(self, request: dict[str, Any]) -> None:
        if self._episode_id is None:
            raise ProtocolError("no active episode", status_code=409)

        episode_id = request["episode_id"]
        if not isinstance(episode_id, str) or episode_id != self._episode_id:
            raise ProtocolError(
                "episode_id does not match the active episode",
                status_code=409,
            )

        simulator_step = request["simulator_step"]
        if isinstance(simulator_step, bool) or not isinstance(simulator_step, int):
            raise ProtocolError("simulator_step must be an integer")
        if simulator_step < 0:
            raise ProtocolError("simulator_step must be non-negative")
        if simulator_step != self._expected_simulator_step:
            raise ProtocolError(
                "simulator_step out of sequence: "
                f"expected {self._expected_simulator_step}, got {simulator_step}",
                status_code=409,
            )

        instruction = request["instruction"]
        if not isinstance(instruction, str) or not instruction.strip():
            raise ProtocolError("instruction must be a non-empty string")

    @staticmethod
    def _decode_rgb_png(encoded: object) -> Image.Image:
        if not isinstance(encoded, str) or not encoded:
            raise ProtocolError("rgb_png_base64 must be non-empty base64 text")
        try:
            image_data = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ProtocolError("rgb_png_base64 is not valid base64") from error

        try:
            with Image.open(io.BytesIO(image_data)) as image:
                if image.format != "PNG" or image.mode != "RGB":
                    raise ProtocolError("rgb_png_base64 must contain an RGB PNG")
                image.load()
                return image.copy()
        except ProtocolError:
            raise
        except (UnidentifiedImageError, OSError, ValueError) as error:
            raise ProtocolError(
                "rgb_png_base64 does not contain a valid PNG"
            ) from error

    @staticmethod
    def _action_value(action: object) -> str:
        if isinstance(action, Enum):
            action = action.value
        if not isinstance(action, str):
            raise TypeError("policy action must be a string-valued action")
        if action not in _ALLOWED_ACTIONS:
            raise RuntimeError(f"unsupported policy action: {action!r}")
        return action


class NaVIDAHTTPServer(ThreadingHTTPServer):
    """Threaded localhost server that owns one stateful policy service."""

    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        *,
        service: OfficialNaVIDAHTTPService,
        max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES,
    ) -> None:
        if (
            isinstance(max_request_bytes, bool)
            or not isinstance(max_request_bytes, int)
            or max_request_bytes <= 0
        ):
            raise ValueError("max_request_bytes must be a positive integer")
        self.service = service
        self.max_request_bytes = max_request_bytes
        super().__init__(server_address, _NaVIDARequestHandler)

    def server_close(self) -> None:
        """Close the listening socket and policy without masking socket errors."""

        primary_error: BaseException | None = None
        primary_traceback = None
        try:
            super().server_close()
        except BaseException as error:
            primary_error = error
            primary_traceback = error.__traceback__

        try:
            self.service.close()
        except BaseException:
            if primary_error is None:
                raise

        if primary_error is not None:
            raise primary_error.with_traceback(primary_traceback)


class _NaVIDARequestHandler(BaseHTTPRequestHandler):
    """Translate localhost JSON requests into service calls."""

    server: NaVIDAHTTPServer

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch()

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch()

    def do_PUT(self) -> None:  # noqa: N802
        self._dispatch()

    def do_PATCH(self) -> None:  # noqa: N802
        self._dispatch()

    def do_DELETE(self) -> None:  # noqa: N802
        self._dispatch()

    def do_HEAD(self) -> None:  # noqa: N802
        self._dispatch()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._dispatch()

    def do_TRACE(self) -> None:  # noqa: N802
        self._dispatch()

    def do_CONNECT(self) -> None:  # noqa: N802
        self._dispatch()

    def _dispatch(self) -> None:
        path = urlsplit(self.path).path
        try:
            if self.command == "GET" and path == "/health":
                status = HTTPStatus.OK
                response = self.server.service.health()
            elif self.command == "POST" and path == "/v1/episodes/start":
                status = HTTPStatus.OK
                response = self.server.service.start_episode(self._read_json())
            elif self.command == "POST" and path == "/v1/steps":
                status = HTTPStatus.OK
                response = self.server.service.process_step(self._read_json())
            elif path in {"/health", "/v1/episodes/start", "/v1/steps"}:
                raise ProtocolError(
                    f"method {self.command} is not allowed for {path}",
                    status_code=HTTPStatus.METHOD_NOT_ALLOWED,
                )
            else:
                raise ProtocolError(
                    f"unknown route: {path}",
                    status_code=HTTPStatus.NOT_FOUND,
                )
        except ProtocolError as error:
            status = error.status_code
            response = {"error": str(error)}
        except Exception:
            status = HTTPStatus.INTERNAL_SERVER_ERROR
            response = {"error": "internal server error"}

        self._send_json(int(status), response)

    def _read_json(self) -> object:
        content_type = self.headers.get("Content-Type", "")
        if content_type.partition(";")[0].strip().lower() != "application/json":
            raise ProtocolError(
                "Content-Type must be application/json",
                status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            )

        if self.headers.get("Transfer-Encoding") is not None:
            raise ProtocolError("Transfer-Encoding is not supported")

        content_lengths = self.headers.get_all("Content-Length", failobj=[])
        if len(content_lengths) != 1:
            raise ProtocolError(
                "exactly one Content-Length header is required",
                status_code=HTTPStatus.LENGTH_REQUIRED,
            )
        try:
            content_length = int(content_lengths[0])
        except (TypeError, ValueError) as error:
            raise ProtocolError("Content-Length must be an integer") from error
        if content_length < 0:
            raise ProtocolError("Content-Length must be non-negative")
        if content_length > self.server.max_request_bytes:
            self.close_connection = True
            raise ProtocolError(
                "request body exceeds maximum size",
                status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )

        body = self.rfile.read(content_length)
        if len(body) != content_length:
            raise ProtocolError("request body ended before Content-Length")
        try:
            return json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ProtocolError("request body must be valid JSON") from error

    def _send_json(self, status_code: int, payload: object) -> None:
        try:
            body = json.dumps(
                payload,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError):
            status_code = HTTPStatus.INTERNAL_SERVER_ERROR
            body = b'{"error":"internal server error"}'

        self.send_response(int(status_code))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        self.close_connection = True

    def send_error(  # type: ignore[override]
        self,
        code: int,
        message: str | None = None,
        explain: str | None = None,
    ) -> None:
        """Replace BaseHTTPRequestHandler's HTML errors with JSON."""

        del explain
        self._send_json(code, {"error": message or HTTPStatus(code).phrase})

    def log_message(self, format: str, *args: object) -> None:
        """Suppress noisy default stderr request logging."""

        del format, args


def create_http_server(
    *,
    policy: Any,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES,
) -> NaVIDAHTTPServer:
    """Construct a bound server around an injected policy without loading it."""

    service = OfficialNaVIDAHTTPService(policy=policy)
    try:
        return NaVIDAHTTPServer(
            (host, port),
            service=service,
            max_request_bytes=max_request_bytes,
        )
    except BaseException:
        try:
            service.close()
        except BaseException:
            pass
        raise

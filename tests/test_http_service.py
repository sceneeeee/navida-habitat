"""Tests for the Official NaVIDA localhost HTTP service."""

from __future__ import annotations

import base64
import http.client
import io
import json
import runpy
import threading
import unittest
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

import navida_habitat
from navida_habitat.action_chunk import HabitatAction
from navida_habitat.http_service import (
    NaVIDAHTTPServer,
    OfficialNaVIDAHTTPService,
    ProtocolError,
    create_http_server,
)


def rgb_png_base64(color: tuple[int, int, int] = (1, 2, 3)) -> str:
    """Return a small lossless RGB PNG as base64 text."""

    buffer = io.BytesIO()
    Image.new("RGB", (3, 2), color).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def encoded_image(*, image_format: str, mode: str = "RGB") -> str:
    """Return a tiny encoded image for request-validation tests."""

    buffer = io.BytesIO()
    color: object = (1, 2, 3, 255) if mode == "RGBA" else (1, 2, 3)
    Image.new(mode, (2, 2), color).save(buffer, format=image_format)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


@dataclass(frozen=True)
class FakeDecision:
    episode_id: str
    decision_step: int
    raw_output: str
    atomic_actions: tuple[object, ...]
    valid: bool = True
    error: str | None = None
    latency_seconds: float = 0.5
    metadata: dict[str, object] = field(
        default_factory=lambda: {"sampled_history_count": 0}
    )


class FakePolicy:
    """Record public policy calls without constructing a model runtime."""

    protocol = "paper_pure"

    def __init__(self, decisions: tuple[FakeDecision, ...] = ()) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.decisions = list(decisions)

    def reset(self, episode_id: str) -> None:
        self.calls.append(("reset", episode_id))

    def observe(self, rgb: Image.Image) -> None:
        self.calls.append(("observe", rgb.mode, rgb.size, rgb.getpixel((0, 0))))

    def act(self, *, instruction: str, decision_step: int) -> FakeDecision:
        self.calls.append(("act", instruction, decision_step))
        return self.decisions.pop(0)

    def close(self) -> None:
        self.calls.append(("close",))


def request_json(
    host: str,
    port: int,
    method: str,
    path: str,
    body: bytes | None = None,
) -> tuple[int, str | None, dict[str, object]]:
    """Issue one loopback request and decode its JSON response."""

    connection = http.client.HTTPConnection(host, port, timeout=2)
    headers = {"Content-Type": "application/json"} if body is not None else {}
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    result = (
        response.status,
        response.getheader("Content-Type"),
        json.loads(response.read()),
    )
    connection.close()
    return result


class OfficialNaVIDAHTTPServiceTest(unittest.TestCase):
    def test_public_service_types_are_exported_without_the_handler(self) -> None:
        self.assertIs(
            navida_habitat.OfficialNaVIDAHTTPService,
            OfficialNaVIDAHTTPService,
        )
        self.assertIs(navida_habitat.NaVIDAHTTPServer, NaVIDAHTTPServer)
        self.assertIs(navida_habitat.ProtocolError, ProtocolError)
        self.assertIs(navida_habitat.create_http_server, create_http_server)
        self.assertFalse(hasattr(navida_habitat, "NaVIDARequestHandler"))

    def test_health_is_static_and_does_not_call_the_policy(self) -> None:
        policy = FakePolicy()
        service = OfficialNaVIDAHTTPService(policy=policy)

        response = service.health()

        self.assertEqual(
            response,
            {
                "status": "ok",
                "policy": "official_navida",
                "protocol": "paper_pure",
            },
        )
        self.assertEqual(policy.calls, [])

    def test_first_step_observes_then_infers_at_decision_step_zero(self) -> None:
        decision = FakeDecision(
            episode_id="episode-1",
            decision_step=0,
            raw_output="forward 25 cm",
            atomic_actions=("move_forward",),
        )
        policy = FakePolicy((decision,))
        service = OfficialNaVIDAHTTPService(policy=policy)

        start_response = service.start_episode({"episode_id": "episode-1"})
        step_response = service.process_step(
            {
                "episode_id": "episode-1",
                "simulator_step": 0,
                "instruction": "Walk forward.",
                "rgb_png_base64": rgb_png_base64(),
            }
        )

        self.assertEqual(
            start_response,
            {"episode_id": "episode-1", "reset": True},
        )
        self.assertEqual(
            policy.calls,
            [
                ("reset", "episode-1"),
                ("observe", "RGB", (3, 2), (1, 2, 3)),
                ("act", "Walk forward.", 0),
            ],
        )
        self.assertEqual(
            step_response,
            {
                "episode_id": "episode-1",
                "simulator_step": 0,
                "decision_step": 0,
                "action": "move_forward",
                "valid": True,
                "inferred": True,
                "raw_output": "forward 25 cm",
                "error": None,
                "termination_reason": None,
                "latency_seconds": 0.5,
                "metadata": {"sampled_history_count": 0},
            },
        )

    def test_queued_actions_observe_each_step_without_another_inference(self) -> None:
        decision = FakeDecision(
            episode_id="queued",
            decision_step=0,
            raw_output="forward 25 cm, turn left 15 degree",
            atomic_actions=(
                HabitatAction.MOVE_FORWARD,
                HabitatAction.TURN_LEFT,
            ),
            latency_seconds=1.25,
            metadata={"last_action": HabitatAction.TURN_LEFT},
        )
        policy = FakePolicy((decision,))
        service = OfficialNaVIDAHTTPService(policy=policy)
        service.start_episode({"episode_id": "queued"})

        first = service.process_step(
            {
                "episode_id": "queued",
                "simulator_step": 0,
                "instruction": "Continue.",
                "rgb_png_base64": rgb_png_base64((1, 2, 3)),
            }
        )
        second = service.process_step(
            {
                "episode_id": "queued",
                "simulator_step": 1,
                "instruction": "Continue.",
                "rgb_png_base64": rgb_png_base64((4, 5, 6)),
            }
        )

        self.assertEqual(first["action"], "move_forward")
        self.assertTrue(first["inferred"])
        self.assertEqual(second["action"], "turn_left")
        self.assertFalse(second["inferred"])
        self.assertEqual(second["decision_step"], 0)
        self.assertEqual(second["raw_output"], decision.raw_output)
        self.assertEqual(second["latency_seconds"], 1.25)
        self.assertEqual(second["error"], None)
        self.assertEqual(second["metadata"], {"last_action": "turn_left"})
        json.dumps(first)
        json.dumps(second)
        self.assertEqual(
            [call[0] for call in policy.calls],
            ["reset", "observe", "act", "observe"],
        )

    def test_decision_step_increments_only_when_queue_needs_inference(self) -> None:
        policy = FakePolicy(
            (
                FakeDecision(
                    episode_id="steps",
                    decision_step=0,
                    raw_output="forward 50 cm",
                    atomic_actions=("move_forward", "move_forward"),
                ),
                FakeDecision(
                    episode_id="steps",
                    decision_step=1,
                    raw_output="turn right 15 degree",
                    atomic_actions=("turn_right",),
                ),
            )
        )
        service = OfficialNaVIDAHTTPService(policy=policy)
        service.start_episode({"episode_id": "steps"})

        responses = [
            service.process_step(
                {
                    "episode_id": "steps",
                    "simulator_step": simulator_step,
                    "instruction": "Continue.",
                    "rgb_png_base64": rgb_png_base64(),
                }
            )
            for simulator_step in range(3)
        ]

        self.assertEqual(
            [response["decision_step"] for response in responses],
            [0, 0, 1],
        )
        self.assertEqual(
            [response["inferred"] for response in responses],
            [True, False, True],
        )
        self.assertEqual(
            [call for call in policy.calls if call[0] == "act"],
            [("act", "Continue.", 0), ("act", "Continue.", 1)],
        )

    def test_episode_start_clears_queue_and_resets_both_step_counters(self) -> None:
        policy = FakePolicy(
            (
                FakeDecision(
                    episode_id="old",
                    decision_step=0,
                    raw_output="forward 50 cm",
                    atomic_actions=("move_forward", "move_forward"),
                ),
                FakeDecision(
                    episode_id="new",
                    decision_step=0,
                    raw_output="stop",
                    atomic_actions=("stop",),
                ),
            )
        )
        service = OfficialNaVIDAHTTPService(policy=policy)
        service.start_episode({"episode_id": "old"})
        service.process_step(
            {
                "episode_id": "old",
                "simulator_step": 0,
                "instruction": "Continue.",
                "rgb_png_base64": rgb_png_base64(),
            }
        )

        service.start_episode({"episode_id": "new"})
        response = service.process_step(
            {
                "episode_id": "new",
                "simulator_step": 0,
                "instruction": "Stop.",
                "rgb_png_base64": rgb_png_base64(),
            }
        )

        self.assertEqual(response["decision_step"], 0)
        self.assertEqual(response["action"], "stop")
        self.assertTrue(response["inferred"])
        self.assertEqual(
            [call for call in policy.calls if call[0] == "reset"],
            [("reset", "old"), ("reset", "new")],
        )

    def test_invalid_model_output_returns_no_fallback_and_stop_is_unchanged(
        self,
    ) -> None:
        policy = FakePolicy(
            (
                FakeDecision(
                    episode_id="invalid",
                    decision_step=0,
                    raw_output="go toward the chair",
                    atomic_actions=(),
                    valid=False,
                    error="invalid action chunk grammar",
                ),
                FakeDecision(
                    episode_id="invalid",
                    decision_step=1,
                    raw_output="stop",
                    atomic_actions=(HabitatAction.STOP,),
                ),
            )
        )
        service = OfficialNaVIDAHTTPService(policy=policy)
        service.start_episode({"episode_id": "invalid"})

        invalid = service.process_step(
            {
                "episode_id": "invalid",
                "simulator_step": 0,
                "instruction": "Continue.",
                "rgb_png_base64": rgb_png_base64(),
            }
        )
        stopped = service.process_step(
            {
                "episode_id": "invalid",
                "simulator_step": 1,
                "instruction": "Stop.",
                "rgb_png_base64": rgb_png_base64(),
            }
        )

        self.assertEqual(
            invalid,
            {
                "episode_id": "invalid",
                "simulator_step": 0,
                "decision_step": 0,
                "action": None,
                "valid": False,
                "inferred": True,
                "raw_output": "go toward the chair",
                "error": "invalid action chunk grammar",
                "termination_reason": "invalid_model_output",
                "latency_seconds": 0.5,
                "metadata": {"sampled_history_count": 0},
            },
        )
        self.assertEqual(stopped["action"], "stop")
        self.assertTrue(stopped["valid"])
        self.assertIsNone(stopped["termination_reason"])

    def test_policy_cannot_emit_an_action_outside_the_http_contract(self) -> None:
        policy = FakePolicy(
            (
                FakeDecision(
                    episode_id="unsupported",
                    decision_step=0,
                    raw_output="jump",
                    atomic_actions=("jump",),
                ),
            )
        )
        service = OfficialNaVIDAHTTPService(policy=policy)
        service.start_episode({"episode_id": "unsupported"})

        with self.assertRaisesRegex(RuntimeError, "unsupported policy action"):
            service.process_step(
                {
                    "episode_id": "unsupported",
                    "simulator_step": 0,
                    "instruction": "Continue.",
                    "rgb_png_base64": rgb_png_base64(),
                }
            )

    def test_valid_policy_decision_must_contain_an_atomic_action(self) -> None:
        policy = FakePolicy(
            (
                FakeDecision(
                    episode_id="empty",
                    decision_step=0,
                    raw_output="",
                    atomic_actions=(),
                    valid=True,
                ),
            )
        )
        service = OfficialNaVIDAHTTPService(policy=policy)
        service.start_episode({"episode_id": "empty"})

        with self.assertRaisesRegex(RuntimeError, "no atomic actions"):
            service.process_step(
                {
                    "episode_id": "empty",
                    "simulator_step": 0,
                    "instruction": "Continue.",
                    "rgb_png_base64": rgb_png_base64(),
                }
            )

    def test_malformed_base64_is_rejected_before_observe(self) -> None:
        policy = FakePolicy()
        service = OfficialNaVIDAHTTPService(policy=policy)
        service.start_episode({"episode_id": "bad-base64"})

        with self.assertRaisesRegex(ProtocolError, "valid base64"):
            service.process_step(
                {
                    "episode_id": "bad-base64",
                    "simulator_step": 0,
                    "instruction": "Continue.",
                    "rgb_png_base64": "%%%not-base64%%%",
                }
            )

        self.assertEqual(policy.calls, [("reset", "bad-base64")])

    def test_non_png_invalid_image_and_non_rgb_png_are_rejected(self) -> None:
        invalid_images = {
            "jpeg": encoded_image(image_format="JPEG"),
            "not-image": base64.b64encode(b"not an image").decode("ascii"),
            "rgba-png": encoded_image(image_format="PNG", mode="RGBA"),
        }

        for name, encoded in invalid_images.items():
            with self.subTest(name=name):
                policy = FakePolicy()
                service = OfficialNaVIDAHTTPService(policy=policy)
                service.start_episode({"episode_id": name})

                with self.assertRaises(ProtocolError):
                    service.process_step(
                        {
                            "episode_id": name,
                            "simulator_step": 0,
                            "instruction": "Continue.",
                            "rgb_png_base64": encoded,
                        }
                    )

                self.assertEqual(policy.calls, [("reset", name)])

    def test_bool_and_negative_simulator_steps_are_rejected(self) -> None:
        for simulator_step in (True, False, -1):
            with self.subTest(simulator_step=simulator_step):
                policy = FakePolicy()
                service = OfficialNaVIDAHTTPService(policy=policy)
                service.start_episode({"episode_id": "invalid-step"})

                with self.assertRaises(ProtocolError):
                    service.process_step(
                        {
                            "episode_id": "invalid-step",
                            "simulator_step": simulator_step,
                            "instruction": "Continue.",
                            "rgb_png_base64": rgb_png_base64(),
                        }
                    )

                self.assertEqual(policy.calls, [("reset", "invalid-step")])

    def test_duplicate_skipped_and_out_of_order_steps_are_rejected(self) -> None:
        for simulator_step in (1, 4):
            with self.subTest(kind="skipped", simulator_step=simulator_step):
                policy = FakePolicy()
                service = OfficialNaVIDAHTTPService(policy=policy)
                service.start_episode({"episode_id": "sequence"})
                with self.assertRaisesRegex(ProtocolError, "expected 0") as caught:
                    service.process_step(
                        {
                            "episode_id": "sequence",
                            "simulator_step": simulator_step,
                            "instruction": "Continue.",
                            "rgb_png_base64": rgb_png_base64(),
                        }
                    )
                self.assertEqual(caught.exception.status_code, 409)

        policy = FakePolicy(
            (
                FakeDecision(
                    episode_id="sequence",
                    decision_step=0,
                    raw_output="stop",
                    atomic_actions=("stop",),
                ),
            )
        )
        service = OfficialNaVIDAHTTPService(policy=policy)
        service.start_episode({"episode_id": "sequence"})
        service.process_step(
            {
                "episode_id": "sequence",
                "simulator_step": 0,
                "instruction": "Stop.",
                "rgb_png_base64": rgb_png_base64(),
            }
        )
        for simulator_step in (0, 2):
            with self.subTest(kind="duplicate-or-out-of-order", step=simulator_step):
                with self.assertRaisesRegex(ProtocolError, "expected 1") as caught:
                    service.process_step(
                        {
                            "episode_id": "sequence",
                            "simulator_step": simulator_step,
                            "instruction": "Stop.",
                            "rgb_png_base64": rgb_png_base64(),
                        }
                    )
                self.assertEqual(caught.exception.status_code, 409)

    def test_missing_active_episode_and_wrong_episode_id_are_rejected(self) -> None:
        payload = {
            "episode_id": "wrong",
            "simulator_step": 0,
            "instruction": "Continue.",
            "rgb_png_base64": rgb_png_base64(),
        }
        service = OfficialNaVIDAHTTPService(policy=FakePolicy())
        with self.assertRaisesRegex(ProtocolError, "no active episode") as caught:
            service.process_step(payload)
        self.assertEqual(caught.exception.status_code, 409)

        policy = FakePolicy()
        service = OfficialNaVIDAHTTPService(policy=policy)
        service.start_episode({"episode_id": "right"})
        with self.assertRaisesRegex(ProtocolError, "does not match") as caught:
            service.process_step(payload)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(policy.calls, [("reset", "right")])

    def test_malformed_missing_and_privileged_fields_are_rejected(self) -> None:
        valid_payload = {
            "episode_id": "strict-fields",
            "simulator_step": 0,
            "instruction": "Continue.",
            "rgb_png_base64": rgb_png_base64(),
        }
        invalid_payloads: tuple[object, ...] = (
            [],
            {
                key: value
                for key, value in valid_payload.items()
                if key != "instruction"
            },
            {**valid_payload, "target_distance": "forbidden"},
            {**valid_payload, "unexpected": None},
        )
        policy = FakePolicy()
        service = OfficialNaVIDAHTTPService(policy=policy)
        service.start_episode({"episode_id": "strict-fields"})

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ProtocolError):
                    service.process_step(payload)

        self.assertEqual(policy.calls, [("reset", "strict-fields")])

    def test_episode_start_requires_exactly_one_non_empty_string_id(self) -> None:
        service = OfficialNaVIDAHTTPService(policy=FakePolicy())

        for payload in (
            {},
            {"episode_id": ""},
            {"episode_id": "   "},
            {"episode_id": 3},
            {"episode_id": "episode", "unexpected": None},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ProtocolError):
                    service.start_episode(payload)

    def test_service_closes_the_policy_exactly_once(self) -> None:
        policy = FakePolicy()
        service = OfficialNaVIDAHTTPService(policy=policy)

        service.close()
        service.close()

        self.assertEqual(policy.calls, [("close",)])
        with self.assertRaisesRegex(RuntimeError, "service is closed"):
            service.start_episode({"episode_id": "too-late"})


class OfficialNaVIDAHTTPServerTest(unittest.TestCase):
    def test_localhost_health_and_unknown_route_are_always_json(self) -> None:
        policy = FakePolicy()
        server = create_http_server(policy=policy, port=0)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        host, port = server.server_address

        try:
            connection = http.client.HTTPConnection(host, port, timeout=2)
            connection.request("GET", "/health")
            health_response = connection.getresponse()
            health_body = json.loads(health_response.read())
            connection.close()

            self.assertEqual(health_response.status, 200)
            self.assertEqual(
                health_response.getheader("Content-Type"),
                "application/json; charset=utf-8",
            )
            self.assertEqual(
                health_body,
                {
                    "status": "ok",
                    "policy": "official_navida",
                    "protocol": "paper_pure",
                },
            )
            self.assertEqual(policy.calls, [])

            connection = http.client.HTTPConnection(host, port, timeout=2)
            connection.request("GET", "/missing")
            missing_response = connection.getresponse()
            missing_body = json.loads(missing_response.read())
            connection.close()

            self.assertEqual(missing_response.status, 404)
            self.assertIn("error", missing_body)
            self.assertNotIn("<html", json.dumps(missing_body).lower())
        finally:
            server.shutdown()
            server.server_close()
            server.server_close()
            thread.join(timeout=2)

        self.assertFalse(thread.is_alive())
        self.assertEqual(policy.calls, [("close",)])


class OfficialNaVIDAHTTPServerCLITest(unittest.TestCase):
    def test_cli_builds_lazy_runtime_policy_and_server_with_defaults(self) -> None:
        script_path = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "run_official_navida_http_server.py"
        )
        script = runpy.run_path(str(script_path), run_name="http_server_test")
        parse_args = script["parse_args"]
        build_server = script["build_server"]
        runtime_calls: list[dict[str, object]] = []
        policy_calls: list[dict[str, object]] = []
        server_calls: list[dict[str, object]] = []

        class FakeRuntimeForCLI:
            def __init__(
                self,
                model_path: Path,
                *,
                device: str,
                attention_implementation: str,
            ) -> None:
                runtime_calls.append(
                    {
                        "model_path": model_path,
                        "device": device,
                        "attention_implementation": attention_implementation,
                    }
                )
                self.load_calls = 0

            def load(self) -> None:
                self.load_calls += 1

        def policy_factory(*, runtime: object, protocol: str) -> FakePolicy:
            policy_calls.append({"runtime": runtime, "protocol": protocol})
            return FakePolicy()

        def server_factory(**kwargs: object) -> object:
            server_calls.append(dict(kwargs))
            return object()

        args = parse_args(["--model-path", "relative-model"])
        server = build_server(
            args,
            runtime_factory=FakeRuntimeForCLI,
            policy_factory=policy_factory,
            server_factory=server_factory,
        )

        self.assertIsNotNone(server)
        self.assertEqual(
            runtime_calls,
            [
                {
                    "model_path": Path("relative-model"),
                    "device": "cuda",
                    "attention_implementation": "sdpa",
                }
            ],
        )
        runtime = policy_calls[0]["runtime"]
        self.assertEqual(runtime.load_calls, 0)
        self.assertEqual(policy_calls[0]["protocol"], "paper_pure")
        self.assertEqual(server_calls[0]["host"], "127.0.0.1")
        self.assertEqual(server_calls[0]["port"], 8008)
        self.assertGreater(server_calls[0]["max_request_bytes"], 0)

    def test_build_does_not_double_close_after_server_factory_failure(
        self,
    ) -> None:
        script_path = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "run_official_navida_http_server.py"
        )
        script = runpy.run_path(str(script_path), run_name="http_server_test")
        parse_args = script["parse_args"]
        build_server = script["build_server"]
        policy = FakePolicy()

        def runtime_factory(*args: object, **kwargs: object) -> object:
            del args, kwargs
            return object()

        def policy_factory(*args: object, **kwargs: object) -> FakePolicy:
            del args, kwargs
            return policy

        def failing_server_factory(**kwargs: object) -> object:
            supplied_policy = kwargs["policy"]
            supplied_policy.close()
            raise OSError("bind failed")

        args = parse_args(["--model-path", "model"])
        with self.assertRaisesRegex(OSError, "bind failed"):
            build_server(
                args,
                runtime_factory=runtime_factory,
                policy_factory=policy_factory,
                server_factory=failing_server_factory,
            )

        self.assertEqual(policy.calls, [("close",)])

    def test_server_lifecycle_preserves_serve_error_if_close_also_fails(
        self,
    ) -> None:
        script_path = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "run_official_navida_http_server.py"
        )
        script = runpy.run_path(str(script_path), run_name="http_server_test")
        serve_http_server = script["serve_http_server"]

        class FailingServer:
            close_calls = 0

            def serve_forever(self) -> None:
                raise RuntimeError("primary serve error")

            def server_close(self) -> None:
                self.close_calls += 1
                raise RuntimeError("secondary close error")

        server = FailingServer()
        with self.assertRaisesRegex(RuntimeError, "primary serve error"):
            serve_http_server(server)
        self.assertEqual(server.close_calls, 1)

    def test_http_post_routes_parse_json_and_return_protocol_statuses(self) -> None:
        policy = FakePolicy(
            (
                FakeDecision(
                    episode_id="http-episode",
                    decision_step=0,
                    raw_output="stop",
                    atomic_actions=(HabitatAction.STOP,),
                ),
            )
        )
        server = create_http_server(policy=policy, port=0)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        host, port = server.server_address

        try:
            status, content_type, started = request_json(
                host,
                port,
                "POST",
                "/v1/episodes/start",
                json.dumps({"episode_id": "http-episode"}).encode(),
            )
            self.assertEqual(status, 200)
            self.assertEqual(content_type, "application/json; charset=utf-8")
            self.assertEqual(
                started,
                {"episode_id": "http-episode", "reset": True},
            )

            status, _, step = request_json(
                host,
                port,
                "POST",
                "/v1/steps",
                json.dumps(
                    {
                        "episode_id": "http-episode",
                        "simulator_step": 0,
                        "instruction": "Stop.",
                        "rgb_png_base64": rgb_png_base64(),
                    }
                ).encode(),
            )
            self.assertEqual(status, 200)
            self.assertEqual(step["action"], "stop")
            self.assertTrue(step["inferred"])

            status, _, malformed = request_json(
                host,
                port,
                "POST",
                "/v1/episodes/start",
                b"{not-json",
            )
            self.assertEqual(status, 400)
            self.assertIn("error", malformed)

            status, _, unsupported = request_json(
                host,
                port,
                "PUT",
                "/v1/steps",
                b"{}",
            )
            self.assertEqual(status, 405)
            self.assertIn("error", unsupported)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(policy.calls[-1], ("close",))

    def test_oversized_http_body_is_rejected_before_policy_use(self) -> None:
        policy = FakePolicy()
        server = create_http_server(
            policy=policy,
            port=0,
            max_request_bytes=1,
        )
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        host, port = server.server_address

        try:
            status, content_type, response = request_json(
                host,
                port,
                "POST",
                "/v1/episodes/start",
                b"{}",
            )
            self.assertEqual(status, 413)
            self.assertEqual(content_type, "application/json; charset=utf-8")
            self.assertIn("maximum size", response["error"])
            self.assertEqual(policy.calls, [])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(policy.calls, [("close",)])


if __name__ == "__main__":
    unittest.main()

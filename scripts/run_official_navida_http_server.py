"""Run the Official NaVIDA localhost HTTP server."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from navida_habitat.http_service import (
    DEFAULT_HOST,
    DEFAULT_MAX_REQUEST_BYTES,
    DEFAULT_PORT,
    create_http_server,
)
from navida_habitat.model_runtime import NaVIDAModelRuntime
from navida_habitat.policy import OfficialNaVIDAPolicy


def positive_int(value: str) -> int:
    """Parse a strictly positive integer."""

    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError(
            f"expected a positive integer, got {value!r}"
        )
    return parsed


def port_number(value: str) -> int:
    """Parse a TCP port, allowing zero for an ephemeral port."""

    parsed = int(value)
    if not 0 <= parsed <= 65_535:
        raise argparse.ArgumentTypeError(f"invalid TCP port: {value!r}")
    return parsed


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse server command-line arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", default=DEFAULT_PORT, type=port_number)
    parser.add_argument(
        "--protocol",
        default="paper_pure",
        choices=("paper_pure",),
    )
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--attention-implementation", default="sdpa")
    parser.add_argument(
        "--max-request-bytes",
        default=DEFAULT_MAX_REQUEST_BYTES,
        type=positive_int,
    )
    return parser.parse_args(argv)


def build_server(
    args: argparse.Namespace,
    *,
    runtime_factory: Any = NaVIDAModelRuntime,
    policy_factory: Any = OfficialNaVIDAPolicy,
    server_factory: Any = create_http_server,
) -> Any:
    """Construct the lazy runtime, policy, and bound HTTP server."""

    runtime = runtime_factory(
        args.model_path,
        device=args.device,
        attention_implementation=args.attention_implementation,
    )
    policy = policy_factory(runtime=runtime, protocol=args.protocol)
    return server_factory(
        policy=policy,
        host=args.host,
        port=args.port,
        max_request_bytes=args.max_request_bytes,
    )


def serve_http_server(server: Any) -> None:
    """Serve until interrupted, closing once without masking serve errors."""

    primary_error: BaseException | None = None
    primary_traceback = None
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    except BaseException as error:
        primary_error = error
        primary_traceback = error.__traceback__

    try:
        server.server_close()
    except BaseException:
        if primary_error is None:
            raise

    if primary_error is not None:
        raise primary_error.with_traceback(primary_traceback)


def main() -> None:
    """Build and run the command-line server."""

    args = parse_args()
    server = build_server(args)
    host, port = server.server_address[:2]
    print(
        f"Listening on http://{host}:{port} "
        f"with protocol {args.protocol}",
        flush=True,
    )
    serve_http_server(server)


if __name__ == "__main__":
    main()

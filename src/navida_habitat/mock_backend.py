"""Deterministic raw-text backend for mock episodes."""

from __future__ import annotations

from collections.abc import Sequence

from navida_habitat.episode_interfaces import BackendExhaustedError


class MockBackend:
    """Return configured raw model outputs in order.

    ``call_count`` counts every call to :meth:`infer`, including the call that
    discovers the output sequence is exhausted.
    """

    def __init__(self, outputs: Sequence[str]) -> None:
        self._outputs = tuple(outputs)
        self.call_count = 0

    def infer(self, *, instruction: str, step: int) -> str:
        """Return the next raw output without performing visual inference."""

        del instruction, step
        output_index = self.call_count
        self.call_count += 1
        if output_index >= len(self._outputs):
            raise BackendExhaustedError("mock backend output sequence exhausted")
        return self._outputs[output_index]

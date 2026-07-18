"""Minimal interfaces shared by episode backends and environments."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from navida_habitat.action_chunk import HabitatAction


class BackendExhaustedError(RuntimeError):
    """Raised when a finite backend has no output left."""


class BackendProtocol(Protocol):
    """Produce one raw action response for an episode decision step."""

    def infer(self, *, instruction: str, step: int) -> str:
        """Return raw model-compatible action text."""


class EnvironmentProtocol(Protocol):
    """Execute atomic actions and expose the state needed for episode logs."""

    @property
    def position(self) -> Mapping[str, float]:
        """Return the current agent position."""

    @property
    def rotation_yaw(self) -> float:
        """Return current yaw in degrees."""

    @property
    def done(self) -> bool:
        """Whether the episode has terminated."""

    @property
    def success(self) -> bool:
        """Whether a configured navigation goal was reached."""

    def execute(self, action: HabitatAction) -> None:
        """Execute one atomic action."""

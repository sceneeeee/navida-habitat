"""Minimal deterministic navigation environment without Habitat.

The coordinate convention uses ``+x`` to the agent's right and ``+z`` in the
initial forward direction. A yaw of 0 degrees faces ``+z``. Left turns add to
yaw, right turns subtract from it, and yaw is normalized to ``[-180, 180)``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from navida_habitat.action_chunk import HabitatAction


@dataclass(slots=True)
class MockEnv:
    """Track deterministic state changes for Habitat-sized atomic actions."""

    position_x: float = 0.0
    position_z: float = 0.0
    yaw_degrees: float = 0.0
    done: bool = False
    success: bool = False
    executed_actions: list[HabitatAction] = field(default_factory=list)

    def execute(self, action: HabitatAction) -> None:
        """Execute one 25 cm, 15 degree, or stop atomic action."""

        if self.done:
            raise RuntimeError("cannot execute an action after the episode is done")

        try:
            normalized_action = HabitatAction(action)
        except ValueError as error:
            raise ValueError(f"unsupported atomic action: {action!r}") from error

        if normalized_action is HabitatAction.MOVE_FORWARD:
            yaw_radians = math.radians(self.yaw_degrees)
            self.position_x -= math.sin(yaw_radians) * 0.25
            self.position_z += math.cos(yaw_radians) * 0.25
        elif normalized_action is HabitatAction.TURN_LEFT:
            self.yaw_degrees = self._normalize_yaw(self.yaw_degrees + 15.0)
        elif normalized_action is HabitatAction.TURN_RIGHT:
            self.yaw_degrees = self._normalize_yaw(self.yaw_degrees - 15.0)
        elif normalized_action is HabitatAction.STOP:
            self.done = True
            self.success = True

        self.executed_actions.append(normalized_action)

    @staticmethod
    def _normalize_yaw(yaw_degrees: float) -> float:
        return (yaw_degrees + 180.0) % 360.0 - 180.0

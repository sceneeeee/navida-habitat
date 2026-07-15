"""Parse NaVIDA text action chunks without depending on Habitat."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ActionParseError(ValueError):
    """Raised when model output does not follow the action chunk grammar."""


class ActionKind(str, Enum):
    """Actions represented by the NaVIDA text grammar."""

    STOP = "stop"
    FORWARD = "forward"
    TURN_LEFT = "turn_left"
    TURN_RIGHT = "turn_right"


class HabitatAction(str, Enum):
    """Habitat atomic navigation actions."""

    STOP = "stop"
    MOVE_FORWARD = "move_forward"
    TURN_LEFT = "turn_left"
    TURN_RIGHT = "turn_right"


@dataclass(frozen=True, slots=True)
class ActionSubChunk:
    """One parsed action and its distance or angle, when applicable."""

    kind: ActionKind
    amount: int | None = None


@dataclass(frozen=True, slots=True)
class ActionChunk:
    """An immutable sequence of parsed action sub-chunks."""

    sub_chunks: tuple[ActionSubChunk, ...]


def parse_action_chunk(text: str) -> ActionChunk:
    """Parse one model response using the strict NaVIDA text grammar."""

    normalized = text.strip().lower()
    answer_match = re.fullmatch(
        r"<answer>\s*(.*?)\s*</answer>", normalized, flags=re.DOTALL
    )
    if answer_match:
        normalized = answer_match.group(1)

    sub_chunks = tuple(_parse_sub_chunk(part) for part in normalized.split(","))
    if not 1 <= len(sub_chunks) <= 3:
        raise ActionParseError("an action chunk must contain one to three sub-chunks")
    if any(
        sub_chunk.kind is ActionKind.STOP
        for sub_chunk in sub_chunks[:-1]
    ):
        raise ActionParseError("stop must be the final sub-chunk")

    return ActionChunk(sub_chunks)


def _parse_sub_chunk(text: str) -> ActionSubChunk:
    normalized = text.strip()
    if normalized == "stop":
        return ActionSubChunk(ActionKind.STOP)

    forward_match = re.fullmatch(r"forward\s+([0-9]+)\s+cm", normalized)
    if forward_match:
        amount = _parse_amount(
            forward_match.group(1),
            step=25,
            maximum=75,
            error_message=(
                "forward distance must be a positive multiple of 25 up to 75 cm"
            ),
        )
        return ActionSubChunk(ActionKind.FORWARD, amount)

    turn_match = re.fullmatch(
        r"turn\s+(left|right)\s+([0-9]+)\s+degree", normalized
    )
    if turn_match:
        amount = _parse_amount(
            turn_match.group(2),
            step=15,
            maximum=45,
            error_message=(
                "turn angle must be a positive multiple of 15 up to 45 degree"
            ),
        )
        kind = (
            ActionKind.TURN_LEFT
            if turn_match.group(1) == "left"
            else ActionKind.TURN_RIGHT
        )
        return ActionSubChunk(kind, amount)

    raise ActionParseError("output does not match the action chunk grammar")


def _parse_amount(
    text: str, *, step: int, maximum: int, error_message: str
) -> int:
    try:
        amount = int(text)
    except ValueError as error:
        raise ActionParseError(error_message) from error

    if amount <= 0 or amount > maximum or amount % step != 0:
        raise ActionParseError(error_message)
    return amount


def expand_action_chunk(
    action_chunk: ActionChunk, *, max_sub_chunks: int = 2
) -> tuple[HabitatAction, ...]:
    """Expand parsed sub-chunks into Habitat's atomic actions."""

    atomic_actions: list[HabitatAction] = []
    action_steps = {
        ActionKind.FORWARD: (HabitatAction.MOVE_FORWARD, 25),
        ActionKind.TURN_LEFT: (HabitatAction.TURN_LEFT, 15),
        ActionKind.TURN_RIGHT: (HabitatAction.TURN_RIGHT, 15),
    }

    for sub_chunk in action_chunk.sub_chunks[:max_sub_chunks]:
        if sub_chunk.kind is ActionKind.STOP:
            atomic_actions.append(HabitatAction.STOP)
            break

        if sub_chunk.amount is None:
            raise ValueError("a movement sub-chunk must have an amount")
        atomic_action, step = action_steps[sub_chunk.kind]
        atomic_actions.extend([atomic_action] * (sub_chunk.amount // step))

    return tuple(atomic_actions)

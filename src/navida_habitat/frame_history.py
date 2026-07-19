"""Bounded RGB history using the official NaVIDA sampling rule."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

from PIL import Image


ItemT = TypeVar("ItemT")


def uniform_sample_with_ends(
    data: Sequence[ItemT],
    count: int,
) -> tuple[ItemT, ...]:
    """Uniformly sample items while preserving the first and last entries."""

    if count < 2:
        raise ValueError("sample count must be at least two")

    if len(data) <= count:
        return tuple(data)

    indices = [
        round(index * (len(data) - 1) / (count - 1))
        for index in range(count)
    ]
    return tuple(data[index] for index in indices)


class FrameHistory:
    """Store recent RGB observations and sample historical frames."""

    def __init__(
        self,
        *,
        max_stored_frames: int = 200,
        sample_count: int = 8,
    ) -> None:
        if max_stored_frames <= 0:
            raise ValueError("max_stored_frames must be positive")

        if sample_count < 2:
            raise ValueError("sample_count must be at least two")

        self.max_stored_frames = max_stored_frames
        self.sample_count = sample_count
        self._frames: list[Image.Image] = []

    def __len__(self) -> int:
        return len(self._frames)

    def clear(self) -> None:
        """Remove all observations from the current episode."""

        self._frames.clear()

    def append(self, frame: Image.Image) -> None:
        """Append an independent RGB copy of one observation."""

        self._frames.append(frame.convert("RGB").copy())

        if len(self._frames) > self.max_stored_frames:
            del self._frames[0]

    @property
    def latest(self) -> Image.Image:
        """Return the most recent captured observation."""

        if not self._frames:
            raise RuntimeError("frame history is empty")

        return self._frames[-1]

    def sample_before_latest(self) -> tuple[Image.Image, ...]:
        """Sample history while reserving the latest frame as current."""

        if len(self._frames) <= 1:
            return ()

        return uniform_sample_with_ends(
            self._frames[:-1],
            self.sample_count,
        )

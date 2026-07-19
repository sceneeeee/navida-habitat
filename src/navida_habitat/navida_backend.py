"""NaVIDA episode backend backed by the current Habitat RGB observation."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from PIL import Image

from navida_habitat.frame_history import FrameHistory
from navida_habitat.model_runtime import (
    NaVIDAGenerationResult,
)


class RGBObservationProvider(Protocol):
    """Expose the most recent RGB observation."""

    @property
    def rgb_observation(self) -> Any:
        """Return a PIL-compatible RGB or RGBA array."""


class NaVIDARuntimeProtocol(Protocol):
    """Runtime interface required by the episode backend."""

    def generate(
        self,
        *,
        instruction: str,
        history_images: Sequence[Image.Image],
        current_image: Image.Image,
    ) -> NaVIDAGenerationResult:
        """Generate one raw action response."""


def observation_to_rgb_image(
    observation: Any,
    *,
    size: tuple[int, int] = (308, 252),
) -> Image.Image:
    """Convert a Habitat RGB or RGBA observation into NaVIDA input."""

    if isinstance(observation, Image.Image):
        image = observation
    else:
        image = Image.fromarray(observation)

    return image.convert("RGB").resize(size)


class NaVIDABackend:
    """Connect Habitat observations to the NaVIDA model runtime."""

    def __init__(
        self,
        *,
        runtime: NaVIDARuntimeProtocol,
        observation_provider: RGBObservationProvider,
        max_action_history: int = 200,
        history_sample_count: int = 8,
        image_size: tuple[int, int] = (308, 252),
    ) -> None:
        self.runtime = runtime
        self.observation_provider = observation_provider
        self.image_size = image_size
        self.frame_history = FrameHistory(
            max_stored_frames=max_action_history,
            sample_count=history_sample_count,
        )
        self.last_result: NaVIDAGenerationResult | None = None

    def observe(self) -> None:
        """Capture the provider's current RGB observation."""

        frame = observation_to_rgb_image(
            self.observation_provider.rgb_observation,
            size=self.image_size,
        )
        self.frame_history.append(frame)

    def infer(self, *, instruction: str, step: int) -> str:
        """Generate a raw action chunk from current and historical RGB."""

        if step < 0:
            raise ValueError("step must not be negative")

        if step == 0:
            self.frame_history.clear()
            self.observe()
        elif len(self.frame_history) == 0:
            raise RuntimeError(
                "no observation was captured before this decision step"
            )

        result = self.runtime.generate(
            instruction=instruction,
            history_images=self.frame_history.sample_before_latest(),
            current_image=self.frame_history.latest,
        )

        self.last_result = result
        return result.raw_output

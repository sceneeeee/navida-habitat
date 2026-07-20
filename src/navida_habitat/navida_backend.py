"""NaVIDA episode backend backed by the current Habitat RGB observation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from PIL import Image

from navida_habitat.frame_history import FrameHistory
from navida_habitat.model_runtime import NaVIDAGenerationResult


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


@dataclass(frozen=True, slots=True)
class NaVIDADecisionRecord:
    """Profile one model decision and its visual context."""

    step: int
    stored_frame_count: int
    available_history_count: int
    sampled_history_count: int
    result: NaVIDAGenerationResult

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "step": self.step,
            "stored_frame_count": self.stored_frame_count,
            "available_history_count": self.available_history_count,
            "sampled_history_count": self.sampled_history_count,
            "raw_output": self.result.raw_output,
            "input_token_count": self.result.input_token_count,
            "generated_token_count": self.result.generated_token_count,
            "latency_seconds": self.result.latency_seconds,
            "peak_allocated_gib": self.result.peak_allocated_gib,
            "peak_reserved_gib": self.result.peak_reserved_gib,
        }


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
        self.decision_records: list[NaVIDADecisionRecord] = []

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
            self.decision_records.clear()
            self.last_result = None
            self.observe()
        elif len(self.frame_history) == 0:
            raise RuntimeError(
                "no observation was captured before this decision step"
            )

        history_images = self.frame_history.sample_before_latest()
        current_image = self.frame_history.latest

        result = self.runtime.generate(
            instruction=instruction,
            history_images=history_images,
            current_image=current_image,
        )

        record = NaVIDADecisionRecord(
            step=step,
            stored_frame_count=len(self.frame_history),
            available_history_count=max(
                0,
                len(self.frame_history) - 1,
            ),
            sampled_history_count=len(history_images),
            result=result,
        )

        self.last_result = result
        self.decision_records.append(record)

        return result.raw_output

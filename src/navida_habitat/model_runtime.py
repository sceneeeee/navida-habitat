"""Lazy-loading Hugging Face runtime for the official NaVIDA checkpoint."""

from __future__ import annotations

import base64
import io
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image


SYSTEM_PROMPT = "You are a helpful assistant."

HISTORY_PROMPT = (
    "Imagine you are a robot programmed for navigation tasks. "
    "You have been given a video of historical observations"
)

CURRENT_PROMPT = "and an image of the current observation"


@dataclass(frozen=True, slots=True)
class NaVIDAGenerationSettings:
    """Generation and image-processing settings used by NaVIDA."""

    max_pixels: int = 501_760
    max_new_tokens: int = 512
    temperature: float = 0.2
    top_p: float = 1.0
    repetition_penalty: float = 1.05
    seed: int = 41


@dataclass(frozen=True, slots=True)
class NaVIDAGenerationResult:
    """One raw NaVIDA generation together with runtime measurements."""

    raw_output: str
    input_token_count: int
    generated_token_count: int
    latency_seconds: float
    peak_allocated_gib: float
    peak_reserved_gib: float


def encode_image_data_uri(image: Image.Image) -> str:
    """Encode one RGB PIL image as an inline JPEG data URI."""

    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def build_navigation_messages(
    *,
    instruction: str,
    history_images: Sequence[Image.Image],
    current_image: Image.Image,
) -> list[dict[str, Any]]:
    """Build the multimodal conversation expected by NaVIDA."""

    normalized_instruction = instruction.strip()
    if not normalized_instruction:
        raise ValueError("instruction must not be empty")

    historical_images = tuple(history_images)

    # The official implementation repeats the current observation as the
    # historical input on the first decision step.
    if not historical_images:
        historical_images = (current_image,)

    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": HISTORY_PROMPT,
        }
    ]

    for image in historical_images:
        content.append(
            {
                "type": "image_url",
                "image_url": encode_image_data_uri(image),
            }
        )

    content.extend(
        [
            {
                "type": "text",
                "text": CURRENT_PROMPT,
            },
            {
                "type": "image_url",
                "image_url": encode_image_data_uri(current_image),
            },
            {
                "type": "text",
                "text": (
                    f". Your assigned task is: '{normalized_instruction}'. "
                    "Analyze this series of images to decide your next move, "
                    "which could involve turning left or right by a specific "
                    "degree or moving forward a certain distance."
                ),
            },
        ]
    )

    return [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                }
            ],
        },
        {
            "role": "user",
            "content": content,
        },
    ]


class NaVIDAModelRuntime:
    """Load and execute the official NaVIDA checkpoint on one CUDA device."""

    def __init__(
        self,
        model_path: str | Path,
        *,
        settings: NaVIDAGenerationSettings | None = None,
        device: str = "cuda",
        local_files_only: bool = True,
        attention_implementation: str = "sdpa",
    ) -> None:
        self.model_path = Path(model_path).expanduser().resolve()
        self.settings = settings or NaVIDAGenerationSettings()
        self.device = device
        self.local_files_only = local_files_only
        self.attention_implementation = attention_implementation

        self._torch: Any | None = None
        self._processor: Any | None = None
        self._model: Any | None = None
        self._generation_config: Any | None = None
        self._process_vision_info: Any | None = None

    @property
    def loaded(self) -> bool:
        """Whether model and processor objects have been created."""

        return self._model is not None and self._processor is not None

    def load(self) -> None:
        """Load the processor and a 4-bit NaVIDA model into CUDA memory."""

        if self.loaded:
            return

        if not self.model_path.is_dir():
            raise FileNotFoundError(
                f"NaVIDA model directory does not exist: {self.model_path}"
            )

        import torch
        from qwen_vl_utils import process_vision_info
        from transformers import (
            AutoProcessor,
            BitsAndBytesConfig,
            GenerationConfig,
            Qwen2_5_VLForConditionalGeneration,
        )

        if self.device != "cuda":
            raise ValueError("the Stage 3 runtime currently supports device='cuda'")

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable")

        if not torch.cuda.is_bf16_supported():
            raise RuntimeError("the selected CUDA device does not support BF16")

        torch.manual_seed(self.settings.seed)
        torch.cuda.manual_seed_all(self.settings.seed)

        processor = AutoProcessor.from_pretrained(
            str(self.model_path),
            local_files_only=self.local_files_only,
            use_fast=False,
        )
        processor.image_processor.max_pixels = self.settings.max_pixels

        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )

        model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            str(self.model_path),
            local_files_only=self.local_files_only,
            quantization_config=quantization_config,
            torch_dtype=torch.bfloat16,
            device_map={"": 0},
            low_cpu_mem_usage=True,
            attn_implementation=self.attention_implementation,
        )
        model.eval()
        model.config.use_cache = True

        generation_config = GenerationConfig(
            do_sample=True,
            temperature=self.settings.temperature,
            max_new_tokens=self.settings.max_new_tokens,
            top_p=self.settings.top_p,
            use_cache=True,
            repetition_penalty=self.settings.repetition_penalty,
            num_return_sequences=1,
        )

        self._torch = torch
        self._processor = processor
        self._model = model
        self._generation_config = generation_config
        self._process_vision_info = process_vision_info

    def generate(
        self,
        *,
        instruction: str,
        history_images: Sequence[Image.Image],
        current_image: Image.Image,
    ) -> NaVIDAGenerationResult:
        """Generate one raw NaVIDA action-chunk response."""

        self.load()

        torch = self._require_component(self._torch, "torch")
        processor = self._require_component(self._processor, "processor")
        model = self._require_component(self._model, "model")
        generation_config = self._require_component(
            self._generation_config,
            "generation config",
        )
        process_vision_info = self._require_component(
            self._process_vision_info,
            "vision processor",
        )

        messages = build_navigation_messages(
            instruction=instruction,
            history_images=history_images,
            current_image=current_image,
        )

        prompt = processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        image_inputs, video_inputs = process_vision_info(messages)

        inputs = processor(
            text=[prompt],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        )
        inputs = inputs.to(self.device)

        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()

        start = time.perf_counter()

        with torch.inference_mode():
            generated_ids = model.generate(
                **inputs,
                generation_config=generation_config,
                use_model_defaults=True,
            )

        torch.cuda.synchronize()
        latency_seconds = time.perf_counter() - start

        input_token_count = int(inputs["input_ids"].shape[1])
        generated_only = generated_ids[:, input_token_count:]

        raw_output = processor.batch_decode(
            generated_only,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0].strip()

        return NaVIDAGenerationResult(
            raw_output=raw_output,
            input_token_count=input_token_count,
            generated_token_count=int(generated_only.shape[1]),
            latency_seconds=latency_seconds,
            peak_allocated_gib=(
                torch.cuda.max_memory_allocated() / 1024**3
            ),
            peak_reserved_gib=(
                torch.cuda.max_memory_reserved() / 1024**3
            ),
        )

    @staticmethod
    def _require_component(component: Any | None, name: str) -> Any:
        if component is None:
            raise RuntimeError(f"NaVIDA {name} is not loaded")
        return component

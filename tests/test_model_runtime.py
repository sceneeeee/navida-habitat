"""Tests for the pure-Python parts of the NaVIDA model runtime."""

from __future__ import annotations

import base64
import unittest

from PIL import Image

from navida_habitat.model_runtime import (
    NaVIDAGenerationSettings,
    build_navigation_messages,
    encode_image_data_uri,
)


class ModelRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.current_image = Image.new("RGB", (32, 24), (10, 20, 30))

    def test_encodes_jpeg_data_uri(self) -> None:
        data_uri = encode_image_data_uri(self.current_image)

        prefix = "data:image/jpeg;base64,"
        self.assertTrue(data_uri.startswith(prefix))

        payload = data_uri.removeprefix(prefix)
        decoded = base64.b64decode(payload)

        self.assertTrue(decoded.startswith(b"\xff\xd8"))
        self.assertTrue(decoded.endswith(b"\xff\xd9"))

    def test_first_step_repeats_current_as_history(self) -> None:
        messages = build_navigation_messages(
            instruction="Walk toward the doorway.",
            history_images=[],
            current_image=self.current_image,
        )

        user_content = messages[1]["content"]
        image_items = [
            item
            for item in user_content
            if item["type"] == "image_url"
        ]

        self.assertEqual(len(image_items), 2)
        self.assertEqual(
            image_items[0]["image_url"],
            image_items[1]["image_url"],
        )

    def test_preserves_supplied_history_order(self) -> None:
        first = Image.new("RGB", (32, 24), (255, 0, 0))
        second = Image.new("RGB", (32, 24), (0, 255, 0))

        messages = build_navigation_messages(
            instruction="Continue forward.",
            history_images=[first, second],
            current_image=self.current_image,
        )

        user_content = messages[1]["content"]
        image_items = [
            item["image_url"]
            for item in user_content
            if item["type"] == "image_url"
        ]

        self.assertEqual(len(image_items), 3)
        self.assertNotEqual(image_items[0], image_items[1])
        self.assertNotEqual(image_items[1], image_items[2])

    def test_rejects_empty_instruction(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "instruction must not be empty",
        ):
            build_navigation_messages(
                instruction="   ",
                history_images=[],
                current_image=self.current_image,
            )

    def test_official_generation_defaults(self) -> None:
        settings = NaVIDAGenerationSettings()

        self.assertEqual(settings.max_pixels, 501_760)
        self.assertEqual(settings.max_new_tokens, 512)
        self.assertEqual(settings.temperature, 0.2)
        self.assertEqual(settings.top_p, 1.0)
        self.assertEqual(settings.repetition_penalty, 1.05)
        self.assertEqual(settings.seed, 41)


if __name__ == "__main__":
    unittest.main()

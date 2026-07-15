import unittest

from navida_habitat.action_chunk import (
    ActionChunk,
    ActionKind,
    ActionParseError,
    ActionSubChunk,
    HabitatAction,
    expand_action_chunk,
    parse_action_chunk,
)


class ParseActionChunkTests(unittest.TestCase):
    def test_parses_each_legal_action_form(self) -> None:
        cases = {
            "stop": ActionSubChunk(ActionKind.STOP),
            "forward 50 cm": ActionSubChunk(ActionKind.FORWARD, 50),
            "turn left 30 degree": ActionSubChunk(ActionKind.TURN_LEFT, 30),
            "turn right 45 degree": ActionSubChunk(ActionKind.TURN_RIGHT, 45),
        }

        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(
                    parse_action_chunk(text),
                    ActionChunk((expected,)),
                )

    def test_parses_multiple_comma_separated_actions(self) -> None:
        self.assertEqual(
            parse_action_chunk(
                "forward 50 cm, turn left 30 degree, turn right 15 degree"
            ),
            ActionChunk(
                (
                    ActionSubChunk(ActionKind.FORWARD, 50),
                    ActionSubChunk(ActionKind.TURN_LEFT, 30),
                    ActionSubChunk(ActionKind.TURN_RIGHT, 15),
                )
            ),
        )

    def test_accepts_complete_answer_wrapper(self) -> None:
        self.assertEqual(
            parse_action_chunk("<answer>forward 25 cm, stop</answer>"),
            ActionChunk(
                (
                    ActionSubChunk(ActionKind.FORWARD, 25),
                    ActionSubChunk(ActionKind.STOP),
                )
            ),
        )

    def test_ignores_outer_whitespace_and_case(self) -> None:
        self.assertEqual(
            parse_action_chunk(
                "  <ANSWER>  TURN   RIGHT  15   DEGREE , FORWARD 25 CM  </ANSWER>  "
            ),
            ActionChunk(
                (
                    ActionSubChunk(ActionKind.TURN_RIGHT, 15),
                    ActionSubChunk(ActionKind.FORWARD, 25),
                )
            ),
        )

    def test_rejects_every_invalid_output_with_action_parse_error(self) -> None:
        invalid_outputs = {
            "empty output": "",
            "extra explanation": "forward 25 cm because the path is clear",
            "wrong unit": "forward 25 meters",
            "negative distance": "forward -25 cm",
            "zero angle": "turn left 0 degree",
            "invalid forward multiple": "forward 30 cm",
            "invalid turn multiple": "turn right 20 degree",
            "forward over chunk limit": "forward 100 cm",
            "turn over chunk limit": "turn left 60 degree",
            "oversized integer token": f"forward {'9' * 5_000} cm",
            "more than three sub-chunks": (
                "forward 25 cm, turn left 15 degree, "
                "turn right 15 degree, stop"
            ),
            "action after stop": "stop, forward 25 cm",
        }

        for label, text in invalid_outputs.items():
            with self.subTest(case=label):
                with self.assertRaises(ActionParseError):
                    parse_action_chunk(text)


class ExpandActionChunkTests(unittest.TestCase):
    def test_defaults_to_only_the_first_two_sub_chunks(self) -> None:
        parsed = parse_action_chunk(
            "forward 75 cm, turn left 45 degree, turn right 15 degree"
        )

        self.assertEqual(
            expand_action_chunk(parsed),
            (
                HabitatAction.MOVE_FORWARD,
                HabitatAction.MOVE_FORWARD,
                HabitatAction.MOVE_FORWARD,
                HabitatAction.TURN_LEFT,
                HabitatAction.TURN_LEFT,
                HabitatAction.TURN_LEFT,
            ),
        )

    def test_stops_expansion_immediately_after_stop(self) -> None:
        parsed = ActionChunk(
            (
                ActionSubChunk(ActionKind.FORWARD, 25),
                ActionSubChunk(ActionKind.STOP),
                ActionSubChunk(ActionKind.TURN_RIGHT, 15),
            )
        )

        self.assertEqual(
            expand_action_chunk(parsed, max_sub_chunks=3),
            (HabitatAction.MOVE_FORWARD, HabitatAction.STOP),
        )


if __name__ == "__main__":
    unittest.main()

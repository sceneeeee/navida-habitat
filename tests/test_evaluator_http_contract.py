"""Cross-repository HTTP contract smoke without Habitat scenes or model weights.

This runs the imported SURF Habitat-side client against the model-side server
using an injected fake policy. It does not evaluate NaVIDA or Habitat navigation.
"""

from __future__ import annotations

import threading
import unittest
from types import SimpleNamespace

import numpy as np

from habitat_vln.core import NavigationObservation
from habitat_vln.policies.official_navida_http_policy import OfficialNaVIDAHTTPPolicy
from navida_habitat.http_service import create_http_server


class FakePolicy:
    def __init__(self) -> None:
        self.episodes: list[str] = []
        self.observations = 0
        self.decisions = 0
        self.closed = 0

    def reset(self, episode_id: str) -> None:
        self.episodes.append(episode_id)

    def observe(self, rgb: object) -> None:
        self.observations += 1

    def act(self, *, instruction: str, decision_step: int) -> SimpleNamespace:
        self.decisions += 1
        if decision_step == 0:
            return SimpleNamespace(
                decision_step=decision_step,
                raw_output="forward 50 cm",
                valid=True,
                error=None,
                latency_seconds=0.01,
                atomic_actions=("move_forward", "move_forward"),
                metadata={"source": "fake-policy"},
            )
        return SimpleNamespace(
            decision_step=decision_step,
            raw_output="invalid action",
            valid=False,
            error="synthetic invalid output",
            latency_seconds=0.01,
            atomic_actions=(),
            metadata={"source": "fake-policy"},
        )

    def close(self) -> None:
        self.closed += 1


class SURFHTTPContractTest(unittest.TestCase):
    def test_imported_client_with_real_local_http_server(self) -> None:
        fake = FakePolicy()
        server = create_http_server(policy=fake, host="127.0.0.1", port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        client = OfficialNaVIDAHTTPPolicy(base_url=f"http://{host}:{port}", timeout=5.0)
        try:
            client.start_episode("portfolio-contract")
            frame = np.zeros((8, 8, 3), dtype=np.uint8)
            outputs = [
                client.predict(
                    NavigationObservation(
                        rgb=frame,
                        instruction="Walk forward.",
                        step=step,
                    )
                )
                for step in range(3)
            ]

            self.assertEqual(fake.episodes, ["portfolio-contract"])
            self.assertEqual(fake.observations, 3)
            self.assertEqual(fake.decisions, 2)  # queued step does not re-infer
            self.assertEqual([out.action for out in outputs], [
                "move_forward", "move_forward", None
            ])
            self.assertEqual([out.is_valid for out in outputs], [True, True, False])
            self.assertEqual([out.metadata["inferred"] for out in outputs], [
                True, False, True
            ])
            self.assertEqual([out.metadata["decision_step"] for out in outputs], [
                0, 0, 1
            ])
            self.assertEqual(outputs[2].termination_reason, "invalid_model_output")
        finally:
            client.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(fake.closed, 1)


if __name__ == "__main__":
    unittest.main()

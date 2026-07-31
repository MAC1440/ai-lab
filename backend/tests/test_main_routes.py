import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import create_app


class ProductionRouteRegistrationTests(unittest.TestCase):
    def test_health_identifies_the_ai_lab_backend(self):
        response = TestClient(create_app()).get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["service"], "ai-lab-backend")
        self.assertEqual(response.json()["version"], "1.0.0")
        self.assertIn("checkout_id", response.json())
        self.assertIn("source_fingerprint", response.json())

    def test_benchmark_routes_are_registered_on_production_app(self):
        paths = set(create_app().openapi()["paths"])

        self.assertIn("/model-benchmarks/recommendations", paths)
        self.assertIn("/model-benchmarks/run/stream", paths)
        self.assertIn("/reliability-benchmarks/scenarios", paths)
        self.assertIn("/reliability-benchmarks/run/stream", paths)

        response = TestClient(create_app()).get(
            "/model-benchmarks/recommendations"
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["applied"])

    def test_lifespan_closes_terminals_without_awaiting_sync_method(self):
        with patch("main.terminal_service.close_all") as close_all:
            with TestClient(create_app()) as client:
                response = client.get("/health")
                self.assertEqual(response.status_code, 200)

        close_all.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

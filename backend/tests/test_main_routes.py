import unittest

from fastapi.testclient import TestClient

from main import create_app


class ProductionRouteRegistrationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

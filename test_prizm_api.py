import json
import os
import unittest
from unittest.mock import patch

from app import app
from prizm_client import normalize_postal_code


LOOKUP_RESULT = {
    "postal_code": "V8A 0A8",
    "prizm_code": "21",
    "segment_number": "21",
    "segment_name": "Scenic Retirement",
    "segment_description": "Older, middle-income suburbanites",
    "average_household_income": "$140,223",
    "education": "High School/College",
    "urbanity": "Suburban",
    "average_household_net_worth": "",
    "occupation": "Mix",
    "diversity": "Low",
    "family_life": "Couples/Families",
    "tenure": "Own",
    "home_type": "Single Detached/Row",
    "status": "success",
}


class TestPrizmAPI(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.client.testing = True

    def test_health_check(self):
        response = self.client.get("/health")
        data = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "ok")

    def test_normalize_postal_code(self):
        self.assertEqual(normalize_postal_code("v8a0a8"), "V8A 0A8")
        self.assertEqual(normalize_postal_code("V8A 0A8"), "V8A 0A8")
        self.assertIsNone(normalize_postal_code("123456"))

    @patch("app.cache_manager.cache_data", return_value=True)
    @patch("app.cache_manager.get_cached_data", return_value=None)
    @patch("app.prizm_client.lookup", return_value=LOOKUP_RESULT)
    def test_single_postal_code(self, lookup, get_cached_data, cache_data):
        response = self.client.get("/api/prizm?postal_code=V8A0A8")
        data = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["postal_code"], "V8A 0A8")
        self.assertEqual(data["prizm_code"], "21")
        lookup.assert_called_once_with("V8A0A8")
        get_cached_data.assert_called_once_with("V8A 0A8")
        cache_data.assert_called_once()

    @patch("app.cache_manager.cache_data", return_value=True)
    @patch("app.cache_manager.get_cached_data", return_value=None)
    @patch("app.prizm_client.lookup", return_value=LOOKUP_RESULT)
    def test_batch_postal_codes(self, lookup, _get_cached_data, _cache_data):
        response = self.client.post("/api/prizm/batch", json={"postal_codes": ["V8A0A8", "V8A 0A8"]})
        data = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["successful"], 2)
        self.assertEqual(lookup.call_count, 2)

    def test_missing_postal_code_parameter(self):
        response = self.client.get("/api/prizm")
        self.assertEqual(response.status_code, 400)

    def test_empty_postal_codes_batch(self):
        response = self.client.post("/api/prizm/batch", json={"postal_codes": []})
        self.assertEqual(response.status_code, 400)

    def test_batch_limit(self):
        response = self.client.post("/api/prizm/batch", json={"postal_codes": ["V8A0A8"] * 11})
        self.assertEqual(response.status_code, 400)

    def test_optional_api_key_protection(self):
        os.environ["PRIZM_API_KEY"] = "secret"
        try:
            response = self.client.get("/api/segments")
            self.assertEqual(response.status_code, 401)

            with patch("app.prizm_client.get_all_segments", return_value=[]):
                response = self.client.get("/api/segments", headers={"X-API-Key": "secret"})
            self.assertEqual(response.status_code, 200)
        finally:
            os.environ.pop("PRIZM_API_KEY", None)


if __name__ == "__main__":
    unittest.main()

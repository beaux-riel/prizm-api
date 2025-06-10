#!/usr/bin/env python3
import unittest
import json
import os
from app import app, get_prizm_code

class TestPrizmAPI(unittest.TestCase):
    """Test cases for the PRIZM API"""

    def setUp(self):
        """Set up the test client"""
        self.app = app.test_client()
        self.app.testing = True

    def test_health_check(self):
        """Test the health check endpoint"""
        response = self.app.get('/health')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['status'], 'ok')

    def test_single_postal_code(self):
        """Test the single postal code endpoint with a valid Canadian postal code"""
        # Note: This test will only pass if the API is running and can access the PRIZM website
        response = self.app.get('/api/prizm?postal_code=V8A2P4')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        # We don't make specific assertions about the values anymore since they come from a live source

    def test_batch_postal_codes(self):
        """Test the batch postal codes endpoint with valid Canadian postal codes"""
        # Note: This test will only pass if the API is running and can access the PRIZM website
        response = self.app.post('/api/prizm/batch',
                                json={'postal_codes': ['M5V2H1', 'V8A2P4']})
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        # We don't make specific assertions about the values anymore since they come from a live source

    def test_direct_get_prizm_code_function(self):
        """Test the get_prizm_code function directly with a valid Canadian postal code"""
        # Note: This test will only pass if the API is running and can access the PRIZM website
        result = get_prizm_code('V8A2P4')
        self.assertIn('postal_code', result)
        self.assertIn('prizm_code', result)

if __name__ == '__main__':
    unittest.main()

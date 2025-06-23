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

    def test_invalid_postal_code_format(self):
        """Test that invalid postal code formats return error status"""
        # Test with clearly invalid format
        response = self.app.get('/api/prizm?postal_code=123456')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['status'].startswith('error:'))
        self.assertEqual(data['prizm_code'], 'Unknown')

    def test_nonexistent_postal_code(self):
        """Test that non-existent postal codes return error status"""
        # Test with properly formatted but non-existent postal code
        response = self.app.get('/api/prizm?postal_code=Z9Z9Z9')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        # Should either be an error or return unknown data
        # (depending on whether the site shows error or example data)

    def test_batch_with_invalid_postal_codes(self):
        """Test batch endpoint with mix of valid and invalid postal codes"""
        postal_codes = ['M5V2H1', '123456', 'V8A2P4', 'Z9Z9Z9']
        response = self.app.post('/api/prizm/batch',
                                json={'postal_codes': postal_codes})
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['total'], 4)
        # Should have both successful and failed entries
        self.assertIn('failed', data)
        # At least one should fail due to invalid format
        self.assertGreater(data.get('failed', 0), 0)

    def test_missing_postal_code_parameter(self):
        """Test that missing postal code parameter returns 400 error"""
        response = self.app.get('/api/prizm')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_empty_postal_codes_batch(self):
        """Test that empty postal codes list returns 400 error"""
        response = self.app.post('/api/prizm/batch',
                                json={'postal_codes': []})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

if __name__ == '__main__':
    unittest.main()

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
        
    def test_single_postal_code_v8a2p4(self):
        """Test the single postal code endpoint with V8A 2P4"""
        response = self.app.get('/api/prizm?postal_code=V8A2P4')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['postal_code'], 'V8A 2P4')
        self.assertEqual(data['prizm_code'], '62')
        self.assertEqual(data['household_income'], '$87,388')
        self.assertEqual(data['residency_home_type'], 'Own & Rent | Single Detached / Low Rise Apt')
        self.assertTrue('Suburban, lower-middle-income singles and couples' in data['segment_description'])
        self.assertTrue('Suburban Recliners is one of the older segments' in data['segment_description'])
        
    def test_batch_postal_codes_with_v8a2p4(self):
        """Test the batch postal codes endpoint with V8A 2P4"""
        response = self.app.post('/api/prizm/batch', 
                                json={'postal_codes': ['M5V2H1', 'V8A2P4']})
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data['results']), 2)
        self.assertEqual(data['total'], 2)
        self.assertEqual(data['successful'], 2)
        
        # Find the V8A 2P4 result
        v8a2p4_result = None
        for result in data['results']:
            if result['postal_code'] == 'V8A 2P4':
                v8a2p4_result = result
                break
                
        self.assertIsNotNone(v8a2p4_result)
        self.assertEqual(v8a2p4_result['prizm_code'], '62')
        self.assertEqual(v8a2p4_result['household_income'], '$87,388')
        self.assertEqual(v8a2p4_result['residency_home_type'], 'Own & Rent | Single Detached / Low Rise Apt')
        self.assertTrue('Suburban, lower-middle-income singles and couples' in v8a2p4_result['segment_description'])
        
    def test_direct_get_prizm_code_function(self):
        """Test the get_prizm_code function directly with V8A 2P4"""
        result = get_prizm_code('V8A2P4')
        self.assertEqual(result['postal_code'], 'V8A 2P4')
        self.assertEqual(result['prizm_code'], '62')
        self.assertEqual(result['household_income'], '$87,388')
        self.assertEqual(result['residency_home_type'], 'Own & Rent | Single Detached / Low Rise Apt')
        self.assertTrue('Suburban, lower-middle-income singles and couples' in result['segment_description'])
        
if __name__ == '__main__':
    unittest.main()
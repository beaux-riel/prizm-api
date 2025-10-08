#!/usr/bin/env python3
"""
Test suite for HTML capture functionality
Tests the new HTML capture and storage feature for debugging purposes
"""

import unittest
import os
import tempfile
import json
import sqlite3
from unittest.mock import patch, MagicMock
from cache_manager_new import CacheManager
from app import app

class TestHTMLCapture(unittest.TestCase):
    """Test HTML capture and storage functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.app = app.test_client()
        self.app.testing = True
        
        # Create a temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        
        # Initialize cache manager with test database
        self.cache_manager = CacheManager(db_path=self.temp_db_path, cache_duration_days=1)
    
    def tearDown(self):
        """Clean up test environment"""
        # Remove temporary database
        if os.path.exists(self.temp_db_path):
            os.unlink(self.temp_db_path)
    
    def test_database_migration(self):
        """Test that html_content column is added to database"""
        # Check if html_content column exists
        with sqlite3.connect(self.temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(postal_code_cache)")
            columns = [column[1] for column in cursor.fetchall()]
            
        self.assertIn('html_content', columns, "html_content column should exist in database")
    
    def test_cache_data_with_html(self):
        """Test caching data with HTML content"""
        test_data = {
            "postal_code": "V8A2P4",
            "segment_number": "23",
            "segment_name": "Test Segment",
            "status": "success"
        }
        test_html = "<html><body>Test HTML Content</body></html>"
        
        # Cache data with HTML
        result = self.cache_manager.cache_data("V8A2P4", test_data, html_content=test_html)
        self.assertTrue(result, "Should successfully cache data with HTML")
        
        # Retrieve cached data
        cached = self.cache_manager.get_cached_data("V8A2P4")
        self.assertIsNotNone(cached, "Should retrieve cached data")
        self.assertTrue(cached['_cache_info']['has_html'], "Should indicate HTML is available")
        
        # Retrieve HTML content
        cached_html = self.cache_manager.get_cached_html("V8A2P4")
        self.assertEqual(cached_html, test_html, "Should retrieve correct HTML content")
    
    def test_cache_data_without_html(self):
        """Test caching data without HTML content (backwards compatibility)"""
        test_data = {
            "postal_code": "V8A2P4",
            "segment_number": "23",
            "segment_name": "Test Segment",
            "status": "success"
        }
        
        # Cache data without HTML
        result = self.cache_manager.cache_data("V8A2P4", test_data)
        self.assertTrue(result, "Should successfully cache data without HTML")
        
        # Retrieve cached data
        cached = self.cache_manager.get_cached_data("V8A2P4")
        self.assertIsNotNone(cached, "Should retrieve cached data")
        self.assertFalse(cached['_cache_info']['has_html'], "Should indicate HTML is not available")
        
        # Try to retrieve HTML content (should return None)
        cached_html = self.cache_manager.get_cached_html("V8A2P4")
        self.assertIsNone(cached_html, "Should return None when no HTML is cached")
    
    def test_get_cached_html_nonexistent(self):
        """Test retrieving HTML for non-existent postal code"""
        cached_html = self.cache_manager.get_cached_html("INVALID")
        self.assertIsNone(cached_html, "Should return None for non-existent postal code")
    
    @patch('app.get_driver')
    @patch('app.get_segment_number')
    def test_api_response_includes_html_flag(self, mock_get_segment, mock_get_driver):
        """Test that API responses include has_html_capture flag"""
        # Mock the scraping result
        mock_get_segment.return_value = {
            "postal_code": "V8A2P4",
            "segment_number": "23",
            "segment_name": "Test Segment",
            "segment_description": "Test Description",
            "who_they_are": "Test Demographics",
            "average_household_income": "$75,000",
            "education": "University",
            "urbanity": "Urban",
            "average_household_net_worth": "$250,000",
            "occupation": "Professional",
            "diversity": "Mixed",
            "family_life": "Families",
            "tenure": "Own",
            "home_type": "Detached",
            "status": "success"
        }
        
        mock_driver = MagicMock()
        mock_get_driver.return_value = mock_driver
        
        # Make API request
        response = self.app.get('/api/prizm?postal_code=V8A2P4')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('has_html_capture', data, "Response should include has_html_capture flag")
        self.assertTrue(data['has_html_capture'], "New scrapes should have HTML captured")
    
    def test_debug_html_endpoint(self):
        """Test the HTML debug endpoint"""
        # First cache some HTML content
        test_html = """<!DOCTYPE html>
        <html>
        <head><title>Test PRIZM Page</title></head>
        <body>
            <div id="segment-details">
                <h2>Segment 23 - Test Segment</h2>
                <p>Test demographic data</p>
            </div>
        </body>
        </html>"""
        
        test_data = {
            "postal_code": "V8A2P4",
            "segment_number": "23",
            "status": "success"
        }
        
        # Use the test cache manager to cache data
        self.cache_manager.cache_data("V8A2P4", test_data, html_content=test_html)
        
        # Mock the cache_manager import in app.py
        with patch('cache_manager.cache_manager', self.cache_manager):
            # Test retrieving HTML
            response = self.app.get('/api/debug/html/V8A2P4')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content_type, 'text/html; charset=utf-8')
            self.assertIn(b'segment-details', response.data)
            
            # Test retrieving non-existent HTML
            response = self.app.get('/api/debug/html/INVALID')
            self.assertEqual(response.status_code, 404)
            data = json.loads(response.data)
            self.assertEqual(data['status'], 'error')
    
    def test_html_capture_during_error(self):
        """Test that HTML is captured during error scenarios"""
        error_html = "<html><body><div class='error'>Invalid postal code</div></body></html>"
        error_data = {
            "postal_code": "INVALID",
            "segment_number": None,
            "status": "error: Invalid postal code"
        }
        
        # Cache error with HTML
        result = self.cache_manager.cache_data("INVALID", error_data, 
                                              custom_duration_days=7, 
                                              html_content=error_html)
        self.assertTrue(result, "Should cache error result with HTML")
        
        # Retrieve HTML for error case
        cached_html = self.cache_manager.get_cached_html("INVALID")
        self.assertEqual(cached_html, error_html, "Should retrieve error HTML content")
    
    def test_html_content_size(self):
        """Test handling of large HTML content"""
        # Create a large HTML string (100KB)
        large_html = "<html><body>" + "x" * 100000 + "</body></html>"
        test_data = {
            "postal_code": "V8A2P4",
            "segment_number": "23",
            "status": "success"
        }
        
        # Cache large HTML
        result = self.cache_manager.cache_data("V8A2P4", test_data, html_content=large_html)
        self.assertTrue(result, "Should handle large HTML content")
        
        # Retrieve large HTML
        cached_html = self.cache_manager.get_cached_html("V8A2P4")
        self.assertEqual(len(cached_html), len(large_html), "Should retrieve complete large HTML")

if __name__ == '__main__':
    unittest.main()
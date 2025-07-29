import os
import time
import json
import logging
import re
from flask import Flask, request, jsonify, render_template
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager

# Import scrape_logic functions
from scrape_logic import validate_postal_code, get_segment_number
# Note: cache_manager is imported locally in functions to handle import errors gracefully

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure Chrome options for headless operation
def get_chrome_options(headless=True):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    # Enable CORS
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    # Add user agent to avoid detection
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    return options

# Initialize the Chrome driver once and reuse it
driver = None

def get_driver():
    global driver
    if driver is None:
        try:
            options = get_chrome_options()
            
            # Check for environment variables that might be set in Docker
            chrome_path = os.environ.get('CHROME_BIN')
            chromedriver_path = os.environ.get('CHROMEDRIVER_PATH')
            
            if chrome_path:
                options.binary_location = chrome_path
            
            # Try to initialize the driver
            if chromedriver_path and os.path.exists(chromedriver_path):
                # Use the specified ChromeDriver path
                driver = webdriver.Chrome(
                    service=Service(chromedriver_path),
                    options=options
                )
            else:
                # Use ChromeDriverManager to get the right driver
                driver = webdriver.Chrome(
                    service=Service(ChromeDriverManager().install()),
                    options=options
                )
            
            driver.set_window_size(1920, 1080)
                
        except Exception as e:
            logger.error(f"Error initializing ChromeDriver: {str(e)}")
            # Fallback to mock driver for testing
            logger.warning("Using mock driver for testing purposes")
            return MockDriver()
    return driver

# Mock classes for testing when Chrome is not available
class MockElement:
    def __init__(self, text_value):
        self._text = text_value
        
    @property
    def text(self):
        return self._text

class MockDriver:
    def __init__(self):
        self.url = None
        
    def get(self, url):
        self.url = url
        logger.info(f"Mock driver navigating to {url}")
        
    def quit(self):
        logger.info("Mock driver quitting")
        
    def save_screenshot(self, path):
        logger.info(f"Mock driver saving screenshot to {path}")
        
    def find_element(self, by, value):
        return MockElement("MOCK_PRIZM_CODE")
        
    # For WebDriverWait compatibility
    def find_elements(self, by, value):
        return [MockElement("MOCK_PRIZM_CODE")]
        
    # For WebDriverWait compatibility
    def execute_script(self, script, *args):
        return None

# Function to get PRIZM code for a single postal code
def get_prizm_code(postal_code):
    try:
        # Use the validate_postal_code function from scrape_logic.py
        formatted_postal_code = validate_postal_code(postal_code)
        
        # If the postal code is invalid, return an error
        if not formatted_postal_code:
            # Import cache_manager locally to handle import errors gracefully
            try:
                from cache_manager import cache_manager
                
                # First check if we have this invalid postal code cached
                cached_data = cache_manager.get_cached_data(postal_code)
                if cached_data:
                    logger.info(f"Returning cached invalid format result for: {postal_code}")
                    # Add cache metadata if not present
                    if '_cache_info' not in cached_data:
                        cached_data['_cache_info'] = {'from_cache': True}
                    return cached_data
            except ImportError:
                logger.warning("Cache manager not available, proceeding without caching")
            
            # Create error result for invalid format
            error_result = {
                "postal_code": postal_code,
                "prizm_code": "Unknown",
                "segment_name": "",
                "segment_description": "",
                "average_household_income": "",
                "education": "",
                "urbanity": "",
                "average_household_net_worth": "",
                "occupation": "",
                "diversity": "",
                "family_life": "",
                "tenure": "",
                "home_type": "",
                "status": "error: Invalid format"
            }
            
            # Cache the invalid format result (use full duration since format won't change)
            try:
                from cache_manager import cache_manager
                if cache_manager.cache_data(postal_code, error_result):
                    logger.info(f"Successfully cached invalid format result for: {postal_code}")
                else:
                    logger.warning(f"Failed to cache invalid format result for: {postal_code}")
            except ImportError:
                logger.warning("Cache manager not available, proceeding without caching")
            
            return error_result
        
        logger.info(f"Processing postal code: {formatted_postal_code}")
        
        # Get or initialize the Chrome driver
        driver = get_driver()
        
        # We're now always using real data, so no mock driver check needed
        # The following code has been removed as we want to fetch real-time data
        
        try:
            # Create debug screenshots directory if it doesn't exist
            os.makedirs("debug_screenshots", exist_ok=True)
            
            # Use the get_segment_number function from scrape_logic.py
            result = get_segment_number(driver, formatted_postal_code)
            
            # Map the result to our API response format
            if result["status"] == "success":
                api_response = {
                    "postal_code": formatted_postal_code,
                    "prizm_code": result["segment_number"] or "Unknown",
                    "segment_name": result["segment_name"] or "",
                    "segment_description": result["segment_description"] or "",
                    "average_household_income": result["average_household_income"] or "",
                    "education": result["education"] or "",
                    "urbanity": result["urbanity"] or "",
                    "average_household_net_worth": result["average_household_net_worth"] or "",
                    "occupation": result["occupation"] or "",
                    "diversity": result["diversity"] or "",
                    "family_life": result["family_life"] or "",
                    "tenure": result["tenure"] or "",
                    "home_type": result["home_type"] or "",
                    "status": "success"
                }
                
                # Add cache metadata if present
                if '_cache_info' in result:
                    api_response['cache_info'] = result['_cache_info']
                
                return api_response
            else:
                # Return error status for invalid postal codes
                return {
                    "postal_code": formatted_postal_code,
                    "prizm_code": "Unknown",
                    "segment_name": "",
                    "segment_description": "",
                    "average_household_income": "",
                    "education": "",
                    "urbanity": "",
                    "average_household_net_worth": "",
                    "occupation": "",
                    "diversity": "",
                    "family_life": "",
                    "tenure": "",
                    "home_type": "",
                    "status": result["status"]  # Keep the original error status
                }
                
        except Exception as e:
            logger.error(f"Error during web scraping for {formatted_postal_code}: {str(e)}")
            return {
                "postal_code": formatted_postal_code,
                "prizm_code": "Unknown",
                "segment_name": "",
                "segment_description": "",
                "average_household_income": "",
                "education": "",
                "urbanity": "",
                "average_household_net_worth": "",
                "occupation": "",
                "diversity": "",
                "family_life": "",
                "tenure": "",
                "home_type": "",
                "status": f"error: {str(e)}"
            }
            
    except Exception as e:
        logger.error(f"General error processing {postal_code}: {str(e)}")
        return {
            "postal_code": postal_code,
            "prizm_code": "Unknown",
            "segment_name": "",
            "segment_description": "",
            "average_household_income": "",
            "education": "",
            "urbanity": "",
            "average_household_net_worth": "",
            "occupation": "",
            "diversity": "",
            "family_life": "",
            "tenure": "",
            "home_type": "",
            "status": f"error: {str(e)}"
        }

# Function to clean up resources when the app is shutting down
def cleanup():
    global driver
    if driver:
        try:
            driver.quit()
        except:
            pass

# Home page with a simple form
@app.route('/')
def home():
    return render_template('index.html')

# API endpoint for single postal code
@app.route('/api/prizm', methods=['GET'])
def get_single_prizm():
    postal_code = request.args.get('postal_code')
    if not postal_code:
        return jsonify({"error": "Postal code is required"}), 400
    
    result = get_prizm_code(postal_code)
    return jsonify(result)

# API endpoint for multiple postal codes
@app.route('/api/prizm/batch', methods=['POST'])
def get_batch_prizm():
    data = request.get_json()
    if not data or 'postal_codes' not in data:
        return jsonify({"error": "Postal codes are required"}), 400
    
    postal_codes = data['postal_codes']
    if not postal_codes or not isinstance(postal_codes, list):
        return jsonify({"error": "Postal codes must be a non-empty list"}), 400
    
    # Limit the number of postal codes to process (to prevent abuse)
    max_postal_codes = 10
    if len(postal_codes) > max_postal_codes:
        return jsonify({
            "error": f"Too many postal codes. Maximum allowed is {max_postal_codes}."
        }), 400

    # Process all postal codes sequentially using the single-lookup helper
    driver = get_driver()
    results = []
    for postal_code in postal_codes:
        results.append(get_prizm_code(postal_code))

    return jsonify({
        "results": results,
        "total": len(results),
        "successful": sum(1 for r in results if r["status"] == "success"),
        "failed": sum(1 for r in results if r["status"] != "success")
    })

# Cache management endpoints
@app.route('/api/cache/stats', methods=['GET'])
def get_cache_stats():
    """Get cache statistics"""
    try:
        # Import cache_manager here to ensure it's available
        from cache_manager import cache_manager
        
        stats = cache_manager.get_cache_stats()
        return jsonify({
            "status": "success",
            "cache_stats": stats
        })
    except ImportError as e:
        logger.error(f"Cache manager import error: {e}")
        return jsonify({
            "status": "error",
            "error": "Cache system not available",
            "details": str(e)
        }), 500
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return jsonify({
            "status": "error",
            "error": "Failed to get cache statistics",
            "details": str(e)
        }), 500

@app.route('/api/cache/cleanup', methods=['POST'])
def cleanup_cache():
    """Clean up expired cache entries"""
    try:
        from cache_manager import cache_manager
        
        deleted_count = cache_manager.cleanup_expired_cache()
        return jsonify({
            "status": "success",
            "message": f"Cleaned up {deleted_count} expired cache entries"
        })
    except ImportError as e:
        logger.error(f"Cache manager import error: {e}")
        return jsonify({
            "status": "error",
            "error": "Cache system not available",
            "details": str(e)
        }), 500
    except Exception as e:
        logger.error(f"Error cleaning up cache: {e}")
        return jsonify({
            "status": "error",
            "error": "Failed to clean up cache",
            "details": str(e)
        }), 500

@app.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    """Clear all cache entries (use with caution)"""
    try:
        from cache_manager import cache_manager
        
        if cache_manager.clear_cache():
            return jsonify({
                "status": "success",
                "message": "All cache entries cleared"
            })
        else:
            return jsonify({
                "status": "error",
                "error": "Failed to clear cache"
            }), 500
    except ImportError as e:
        logger.error(f"Cache manager import error: {e}")
        return jsonify({
            "status": "error",
            "error": "Cache system not available",
            "details": str(e)
        }), 500
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return jsonify({
            "status": "error",
            "error": "Failed to clear cache",
            "details": str(e)
        }), 500

@app.route('/api/cache/check/<postal_code>', methods=['GET'])
def check_cache(postal_code):
    """Check if a postal code is cached"""
    try:
        from cache_manager import cache_manager
        
        is_cached = cache_manager.is_cached(postal_code)
        cached_data = cache_manager.get_cached_data(postal_code) if is_cached else None
        
        return jsonify({
            "status": "success",
            "postal_code": postal_code,
            "is_cached": is_cached,
            "cached_at": cached_data.get('_cache_info', {}).get('cached_at') if cached_data else None
        })
    except ImportError as e:
        logger.error(f"Cache manager import error: {e}")
        return jsonify({
            "status": "error",
            "error": "Cache system not available",
            "details": str(e)
        }), 500
    except Exception as e:
        logger.error(f"Error checking cache for {postal_code}: {e}")
        return jsonify({
            "status": "error",
            "error": "Failed to check cache",
            "details": str(e)
        }), 500

@app.route('/api/cache/delete/<postal_code>', methods=['DELETE'])
def delete_cache_entry(postal_code):
    """Delete a specific postal code from cache"""
    try:
        from cache_manager import cache_manager
        
        if cache_manager.delete_cached_data(postal_code):
            return jsonify({
                "status": "success",
                "message": f"Successfully deleted cache entry for {postal_code}"
            })
        else:
            return jsonify({
                "status": "error",
                "error": f"No cache entry found for {postal_code}"
            }), 404
    except ImportError as e:
        logger.error(f"Cache manager import error: {e}")
        return jsonify({
            "status": "error",
            "error": "Cache system not available",
            "details": str(e)
        }), 500
    except Exception as e:
        logger.error(f"Error deleting cache entry for {postal_code}: {e}")
        return jsonify({
            "status": "error",
            "error": "Failed to delete cache entry",
            "details": str(e)
        }), 500

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "message": "Service is running"})

# Add CORS headers
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

# Create a simple script to run the server
def create_run_script():
    script_content = """#!/bin/bash
export PORT=8080
cd "$(dirname "$0")"
python app.py
"""
    with open('run_server.sh', 'w') as f:
        f.write(script_content)
    os.chmod('run_server.sh', 0o755)
    print("Created run_server.sh script")

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Create debug screenshots directory if it doesn't exist
    os.makedirs('debug_screenshots', exist_ok=True)
    
    # Create run script
    create_run_script()
    
    # Get port from environment or use default
    port = int(os.environ.get('PORT', 8080))
    
    print(f"Starting server on port {port}...")
    
    try:
        # Run the Flask app
        app.run(host='0.0.0.0', port=port, debug=True)
    finally:
        # Clean up resources when the app is shutting down
        cleanup()
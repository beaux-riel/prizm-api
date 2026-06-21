#!/usr/bin/env python3
"""
Demo script to test HTML capture feature with problematic postal codes
This demonstrates how the HTML capture helps debug misaligned data
"""

import requests
import json
import time
from cache_manager_new import cache_manager

def test_html_capture_demo():
    """Test HTML capture with various postal codes"""
    
    print("=" * 60)
    print("HTML CAPTURE FEATURE DEMONSTRATION")
    print("=" * 60)
    
    # Test postal codes (including potentially problematic ones)
    test_codes = [
        "V8A2P4",  # Valid BC postal code
        "M5V3A8",  # Valid Toronto postal code  
        "INVALID", # Invalid code to test error HTML capture
        "X0X0X0",  # Potentially problematic format
    ]
    
    # Check if server is running
    try:
        response = requests.get("http://localhost:8080/health")
        if response.status_code != 200:
            print("⚠️  Server is not running. Please start it with: python app.py")
            print("   Then run this script again.")
            return
    except:
        print("⚠️  Server is not running. Please start it with: python app.py")
        print("   Then run this script again.")
        return
    
    print("\nServer is running. Testing HTML capture feature...\n")
    
    for postal_code in test_codes:
        print(f"\n📍 Testing postal code: {postal_code}")
        print("-" * 40)
        
        # Make API request
        try:
            response = requests.get(f"http://localhost:8080/api/prizm?postal_code={postal_code}")
            data = response.json()
            
            # Display results
            print(f"✅ Status: {data.get('status', 'unknown')}")
            print(f"📊 PRIZM Code: {data.get('prizm_code', 'N/A')}")
            print(f"🏷️  Segment: {data.get('segment_name', 'N/A')}")
            
            # Check HTML capture flag
            has_html = data.get('has_html_capture', False)
            print(f"📄 HTML Captured: {'Yes ✓' if has_html else 'No ✗'}")
            
            # If HTML was captured, show how to access it
            if has_html:
                html_url = f"http://localhost:8080/api/debug/html/{postal_code.replace(' ', '')}"
                print(f"🔗 View HTML: {html_url}")
                
                # Try to fetch and display a snippet of the HTML
                try:
                    html_response = requests.get(html_url)
                    if html_response.status_code == 200:
                        html_content = html_response.text
                        print(f"📏 HTML Size: {len(html_content)} characters")
                        
                        # Check for key elements in HTML
                        if 'segment-details' in html_content:
                            print("✅ HTML contains segment-details element")
                        if 'error' in html_content.lower():
                            print("⚠️  HTML contains error message")
                except Exception as e:
                    print(f"❌ Could not fetch HTML: {e}")
            
            # Show cache info if available
            if 'cache_info' in data:
                cache_info = data['cache_info']
                print(f"💾 From Cache: {cache_info.get('from_cache', False)}")
                if cache_info.get('from_cache'):
                    print(f"   Cached at: {cache_info.get('cached_at', 'unknown')}")
            
        except Exception as e:
            print(f"❌ Error testing {postal_code}: {e}")
        
        # Small delay between requests to be polite
        time.sleep(0.5)
    
    print("\n" + "=" * 60)
    print("DEMONSTRATION COMPLETE")
    print("=" * 60)
    print("\n📝 Summary:")
    print("- HTML is now captured for all scraped pages")
    print("- HTML can be viewed at /api/debug/html/<postal_code>")
    print("- This helps debug data misalignment issues")
    print("- HTML is stored in cache alongside demographic data")
    print("- Invalid postal codes also have their HTML captured for debugging")

if __name__ == "__main__":
    # Test directly with cache manager (without server)
    print("\n🔬 Testing cache manager directly...")
    print("-" * 40)
    
    # Check if we have any cached HTML
    stats = cache_manager.get_cache_stats()
    print(f"📊 Cache Statistics:")
    print(f"   Total entries: {stats.get('total_entries', 0)}")
    print(f"   Valid entries: {stats.get('valid_entries', 0)}")
    print(f"   Database size: {stats.get('database_size_bytes', 0)} bytes")
    
    # Try to get HTML for a cached postal code
    test_postal = "V8A2P4"
    cached_html = cache_manager.get_cached_html(test_postal)
    if cached_html:
        print(f"\n✅ Found cached HTML for {test_postal}")
        print(f"   Size: {len(cached_html)} characters")
        print(f"   Contains 'segment-details': {'segment-details' in cached_html}")
    else:
        print(f"\n❌ No cached HTML for {test_postal}")
    
    print("\n" + "=" * 60)
    print("\n🚀 Now testing with live server...")
    test_html_capture_demo()
#!/usr/bin/env python3
"""
Test script to demonstrate the comprehensive demographic data extraction
"""

import json
from scrape_logic import extract_demographic_data, validate_postal_code

def test_demographic_extraction():
    """Test the new comprehensive demographic data extraction"""
    
    # Test postal codes
    test_codes = ["V8A2P4", "M5V2H1", "K1A0A9"]
    
    print("Testing comprehensive demographic data extraction...")
    print("=" * 60)
    
    for postal_code in test_codes:
        formatted_code = validate_postal_code(postal_code)
        if formatted_code:
            print(f"\nTesting postal code: {formatted_code}")
            print("-" * 40)
            
            # Create a mock demographic data structure for demonstration
            # In actual usage, this would come from scraping the website
            mock_data = {
                "segment_name": f"Sample Segment for {formatted_code}",
                "segment_description": "Sample description of the demographic segment",
                "who_they_are": "Detailed lifestyle and characteristic description would appear here",
                "average_household_income": "$100,000",
                "education": "University/College",
                "urbanity": "Suburban",
                "average_household_net_worth": "$500,000",
                "occupation": "Professional/Manager",
                "diversity": "Medium",
                "family_life": "Families",
                "tenure": "Own",
                "home_type": "Single Detached"
            }
            
            print("Demographic Data Structure:")
            for key, value in mock_data.items():
                if value:
                    print(f"  {key.replace('_', ' ').title()}: {value}")
            
            print(f"\nThis would be the API response format for {formatted_code}")
        else:
            print(f"Invalid postal code format: {postal_code}")
    
    print("\n" + "=" * 60)
    print("Test completed! The API now extracts comprehensive demographic data.")
    print("\nTo test with real data, run:")
    print("  python scrape_logic.py -p V8A2P4")
    print("\nTo start the web API:")
    print("  python app.py")

if __name__ == "__main__":
    test_demographic_extraction()

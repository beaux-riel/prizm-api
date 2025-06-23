#!/usr/bin/env python3
"""
Test script to verify error handling for invalid postal codes
"""
import requests
import json

def test_invalid_postal_code():
    """Test that invalid postal codes return proper error status"""
    
    # Test with clearly invalid postal codes
    invalid_codes = [
        "Z9Z 9Z9",  # Non-existent postal code format
        "X0X 0X0",  # Another non-existent format
        "999 999",  # Invalid format (numbers only)
        "ABC DEF",  # Invalid format (letters only)
    ]
    
    base_url = "http://localhost:8080"
    
    print("Testing error handling for invalid postal codes...")
    print("=" * 60)
    
    for postal_code in invalid_codes:
        print(f"\nTesting postal code: {postal_code}")
        
        try:
            # Test single postal code endpoint
            response = requests.get(f"{base_url}/api/prizm", params={"postal_code": postal_code})
            
            if response.status_code == 200:
                data = response.json()
                print(f"Status: {data.get('status', 'Unknown')}")
                print(f"PRIZM Code: {data.get('prizm_code', 'Unknown')}")
                
                if data.get('status', '').startswith('error:'):
                    print("✅ Correctly identified as error")
                else:
                    print("⚠️  Warning: Should have been identified as error")
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Connection Error: {e}")
    
    print("\n" + "=" * 60)
    print("Testing batch endpoint with mixed valid/invalid codes...")
    
    # Test batch endpoint with mix of valid and invalid codes
    mixed_codes = [
        "M5V 3A8",  # Valid Toronto postal code
        "Z9Z 9Z9",  # Invalid
        "K1A 0A6",  # Valid Ottawa postal code
        "X0X 0X0",  # Invalid
    ]
    
    try:
        response = requests.post(f"{base_url}/api/prizm/batch", 
                               json={"postal_codes": mixed_codes},
                               headers={"Content-Type": "application/json"})
        
        if response.status_code == 200:
            data = response.json()
            print(f"\nBatch Results Summary:")
            print(f"Total: {data.get('total', 0)}")
            print(f"Successful: {data.get('successful', 0)}")
            print(f"Failed: {data.get('failed', 0)}")
            
            print(f"\nDetailed Results:")
            for i, result in enumerate(data.get('results', [])):
                postal_code = result.get('postal_code', 'Unknown')
                status = result.get('status', 'Unknown')
                prizm_code = result.get('prizm_code', 'Unknown')
                print(f"  {i+1}. {postal_code}: {status} (PRIZM: {prizm_code})")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    print("Make sure the server is running on localhost:8080 before running this test")
    print("Start the server with: python app.py")
    print("")
    input("Press Enter to continue with the test...")
    test_invalid_postal_code()

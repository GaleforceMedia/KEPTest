import requests
import json

# Your provided credentials
API_KEY = "i043Uc7SRU6Zxs2GfxGk4QmWa4SxA6Ac"
API_SECRET = "oaRzDeAhrwHmHmGy"

# Provide ONE real tracking number to test
TRACKING_NUMBER = "60120248924824" 

def test_dhl_api():
    url = "https://api-eu.dhl.com/track/shipments"
    
    # Standard DHL Tracking usually only requires the API Key in the header
    headers = {
        "DHL-API-Key": API_KEY
    }
    
    params = {
        "trackingNumber": TRACKING_NUMBER
    }
    
    print(f"Connecting to DHL API for tracking number: {TRACKING_NUMBER}...")
    
    try:
        # We also pass the secret in basic auth just in case your specific DHL app tier requires it
        response = requests.get(url, headers=headers, params=params, auth=(API_KEY, API_SECRET))
        
        print(f"\nHTTP Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("\n✅ SUCCESS! DHL responded with data:\n")
            print(json.dumps(response.json(), indent=2))
        elif response.status_code == 429:
            print("\n❌ RATE LIMIT EXCEEDED (429): You have used your 250 requests for today.")
        elif response.status_code == 401:
            print("\n❌ UNAUTHORIZED (401): The API Key or Secret is incorrect or not active for this endpoint.")
            print("Response:", response.text)
        else:
            print(f"\n❌ ERROR: {response.status_code}")
            print("Response:", response.text)
            
    except Exception as e:
        print(f"\n❌ CRITICAL FAILURE: {e}")

if __name__ == "__main__":
    test_dhl_api()

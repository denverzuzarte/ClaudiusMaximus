"""
Quick test script to verify API integration
Run this after starting the API server
"""
import requests
import json

API_URL = "http://localhost:5001"

def test_health():
    """Test health endpoint"""
    print("Testing /api/health...")
    response = requests.get(f"{API_URL}/api/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

def test_policy():
    """Test policy endpoint"""
    print("Testing /api/policy...")
    response = requests.get(f"{API_URL}/api/policy")
    print(f"Status: {response.status_code}")
    print(f"Policy loaded: {len(response.json())} rules")
    print()

def test_execute():
    """Test execution endpoint"""
    print("Testing /api/execute...")
    payload = {"text": "Pay my electricity bill"}
    response = requests.post(
        f"{API_URL}/api/execute",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Execution ID: {data.get('execution_id')}")
    print(f"Stages: {len(data.get('stages', []))}")
    print(f"Final outcome: {data['stages'][-1]['payload']['status']}")
    print()
    
    # Pretty print the full response
    print("Full execution trace:")
    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    print("=" * 50)
    print("ArmourIQ API Integration Test")
    print("=" * 50)
    print()
    
    try:
        test_health()
        test_policy()
        test_execute()
        
        print("=" * 50)
        print("✓ All tests passed!")
        print("=" * 50)
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to API server")
        print("Make sure the server is running: python api/server.py")
    except Exception as e:
        print(f"ERROR: {str(e)}")

"""
Test script to demonstrate sophisticated policy validation
"""
import json
import requests

BASE_URL = "http://localhost:5001"

def test_policy(test_name, request_text, responses):
    """Test a policy scenario"""
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print(f"{'='*80}")
    
    body = {
        "text": request_text,
        "responses": responses
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/execute-with-intent",
            json=body,
            timeout=40
        )
        data = response.json()
        
        # Find MCP_OUTCOME stage
        outcome = next((s for s in data['stages'] if s['type'] == 'MCP_OUTCOME'), None)
        
        if outcome:
            payload = outcome['payload']
            status = payload.get('status')
            
            print(f"\n📊 STATUS: {status}")
            print(f"💯 Confidence: {int(payload.get('confidence', 0) * 100)}%")
            
            if payload.get('triggered_rules'):
                print(f"\n⚖️  TRIGGERED RULES:")
                for rule in payload['triggered_rules']:
                    print(f"   • {rule}")
            
            if payload.get('failures'):
                print(f"\n❌ POLICY VIOLATIONS:")
                for failure in payload['failures']:
                    severity = failure.get('severity', 'UNKNOWN')
                    category = failure.get('category', 'UNKNOWN')
                    reason = failure.get('reason', '')
                    
                    icon = {
                        'BLOCK': '🚫',
                        'BLOCK_AND_LOG': '🚨',
                        'REQUIRE_HUMAN_APPROVAL': '⚠️'
                    }.get(severity, '❓')
                    
                    print(f"\n   {icon} [{severity}]")
                    print(f"      Category: {category}")
                    print(f"      Reason: {reason}")
            
            if status == 'APPROVED' and payload.get('payment_url'):
                print(f"\n✅ Payment URL: {payload['payment_url']}")
            
            return status
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return None


if __name__ == "__main__":
    print("\n🎯 SOPHISTICATED POLICY VALIDATION DEMONSTRATION")
    print("=" * 80)
    
    # Test 1: Blacklisted destination
    test_policy(
        "Blacklisted Destination (Syria)",
        "book hotel in damascus",
        [
            {"id": "q1", "answer": "damascus, syria", "field": "location", "step": 1},
            {"id": "q2", "answer": "april 1 2026", "field": "check_in", "step": 2},
            {"id": "q3", "answer": "april 5 2026", "field": "check_out", "step": 3},
            {"id": "q4", "answer": "1", "field": "travelers", "step": 4},
            {"id": "q5", "answer": "100 usd per night", "field": "budget", "step": 5}
        ]
    )
    
    # Test 2: Last-minute international flight
    test_policy(
        "Last-Minute International Flight (< 72 hours)",
        "book flight from new delhi to paris tomorrow",
        [
            {"id": "q1", "answer": "new delhi", "field": "origin", "step": 1},
            {"id": "q2", "answer": "paris", "field": "destination", "step": 2},
            {"id": "q3", "answer": "february 9 2026", "field": "departure_date", "step": 3},
            {"id": "q4", "answer": "1", "field": "travelers", "step": 4},
            {"id": "q5", "answer": "80000 rupees", "field": "budget", "step": 5}
        ]
    )
    
    # Test 3: Valid booking (should APPROVE)
    test_policy(
        "Valid Booking (Should APPROVE)",
        "book hotel in tokyo",
        [
            {"id": "q1", "answer": "shinjuku, tokyo", "field": "location", "step": 1},
            {"id": "q2", "answer": "march 20 2026", "field": "check_in", "step": 2},
            {"id": "q3", "answer": "march 23 2026", "field": "check_out", "step": 3},
            {"id": "q4", "answer": "2", "field": "travelers", "step": 4},
            {"id": "q5", "answer": "15000 yen per night", "field": "budget", "step": 5}
        ]
    )
    
    print(f"\n{'='*80}")
    print("✅ Policy validation demonstration complete!")
    print(f"{'='*80}\n")

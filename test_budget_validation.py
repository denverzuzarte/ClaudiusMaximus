"""
Test budget validation - user's budget vs AI's recommended price
"""
import requests
import json

BASE_URL = "http://localhost:5001"

print("\n" + "="*80)
print("🔍 TESTING BUDGET VALIDATION")
print("="*80)

# Simulating the Sydney-Brisbane case:
# User budget: 2000 INR (≈36 AUD)
# AI recommends: 79 AUD (≈4350 INR)
# That's 217.5% of budget (117.5% OVER budget)

test_cases = [
    {
        "name": "Budget Exceeded (Sydney-Brisbane case)",
        "request": "book flight from sydney to brisbane",
        "responses": [
            {"id": "q1", "answer": "sydney", "field": "origin", "step": 1},
            {"id": "q2", "answer": "brisbane", "field": "destination", "step": 2},
            {"id": "q3", "answer": "june 15 2026", "field": "departure_date", "step": 3},
            {"id": "q4", "answer": "1", "field": "travelers", "step": 4},
            {"id": "q5", "answer": "2000 INR", "field": "budget", "step": 5},  # User's budget
        ],
        "expected": "BLOCKED or REQUIRES_APPROVAL (price 4350 INR vs budget 2000 INR)"
    },
    {
        "name": "Budget Met (Within budget)",
        "request": "book hotel in tokyo",
        "responses": [
            {"id": "q1", "answer": "shinjuku, tokyo", "field": "location", "step": 1},
            {"id": "q2", "answer": "march 20 2026", "field": "check_in", "step": 2},
            {"id": "q3", "answer": "march 23 2026", "field": "check_out", "step": 3},
            {"id": "q4", "answer": "2", "field": "travelers", "step": 4},
            {"id": "q5", "answer": "20000 yen per night", "field": "budget", "step": 5},
        ],
        "expected": "APPROVED (price within budget)"
    }
]

for i, test in enumerate(test_cases, 1):
    print(f"\n{'='*80}")
    print(f"TEST {i}: {test['name']}")
    print(f"{'='*80}")
    print(f"Expected: {test['expected']}\n")
    
    body = {
        "text": test["request"],
        "responses": test["responses"]
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/execute-with-intent",
            json=body,
            timeout=40
        )
        data = response.json()
        
        print(f"Response status: {response.status_code}")
        print(f"Response keys: {data.keys() if isinstance(data, dict) else 'Not a dict'}")
        
        if 'error' in data:
            print(f"❌ API Error: {data['error']}")
            continue
        
        # Find outcome
        outcome = next((s for s in data['stages'] if s['type'] == 'MCP_OUTCOME'), None)
        
        if outcome:
            payload = outcome['payload']
            status = payload.get('status')
            
            print(f"📊 ACTUAL RESULT:")
            print(f"   Status: {status}")
            print(f"   Confidence: {int(payload.get('confidence', 0) * 100)}%")
            
            if payload.get('triggered_rules'):
                print(f"\n⚖️  Triggered Rules:")
                for rule in payload['triggered_rules']:
                    print(f"      • {rule}")
            
            if payload.get('failures'):
                print(f"\n❌ Policy Violations:")
                for failure in payload['failures']:
                    severity = failure.get('severity', '')
                    category = failure.get('category', '')
                    reason = failure.get('reason', '')
                    
                    icon = {
                        'BLOCK': '🚫',
                        'BLOCK_AND_LOG': '🚨',
                        'REQUIRE_HUMAN_APPROVAL': '⚠️'
                    }.get(severity, '❓')
                    
                    print(f"\n      {icon} [{severity}]")
                    print(f"         Category: {category}")
                    print(f"         Reason: {reason}")
            
            # Verify correctness
            if test['name'].startswith("Budget Exceeded"):
                if status in ['BLOCKED', 'REQUIRES_APPROVAL']:
                    print(f"\n✅ CORRECT: Budget validation working!")
                else:
                    print(f"\n❌ INCORRECT: Should be BLOCKED/REQUIRES_APPROVAL, got {status}")
            elif test['name'].startswith("Budget Met"):
                if status == 'APPROVED':
                    print(f"\n✅ CORRECT: Approved as expected!")
                else:
                    print(f"\n⚠️  UNEXPECTED: Should be APPROVED, got {status}")
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        print(traceback.format_exc())

print(f"\n{'='*80}")
print("✅ Budget validation test complete!")
print(f"{'='*80}\n")

# ArmourIQ Integration Guide

## System Architecture

The ArmourIQ system consists of three main layers that work together to provide policy-enforced execution monitoring:

### 1. Frontend Layer (demo-ui)
**Technology:** React + Vite  
**Port:** 5174  
**Purpose:** User interface and execution visualization

**Key Components:**
- `App.jsx` - Main application with API integration
- `StageCard.jsx` - Individual execution stage renderer
- `App.css` / `StageCard.css` - Enterprise-grade styling

**Flow:**
1. User enters transaction request
2. Frontend sends POST request to Backend API
3. Receives execution trace with 6 stages
4. Renders each stage visually
5. Falls back to mock data if API unavailable

### 2. Backend API Layer (api)
**Technology:** Flask + YAML  
**Port:** 5001  
**Purpose:** Policy evaluation and trace generation

**Key Components:**
- `server.py` - REST API endpoints
- Policy evaluation engine
- Execution trace builder
- Integration with `manager/policy_travel.yaml`

**Endpoints:**
```
POST /api/execute
{
  "text": "Pay my electricity bill"
}
→ Returns full execution trace with policy evaluation

GET /api/policy
→ Returns current policy configuration

GET /api/health
→ Health check
```

**Policy Evaluation Logic:**
```python
def evaluate_payment_policy(amount: float, merchant: str):
    # Check 1: Merchant allowlist
    verified_merchants = ['ELECTRICITY_BOARD', 'WATER_UTILITY', 'TELECOM_PROVIDER']
    
    # Check 2: Transaction limits
    if merchant in verified_merchants:
        max_amount = 50000  # From policy YAML
    else:
        max_amount = 5000   # Unverified vendor limit
    
    # Check 3: Amount validation
    if amount > 5000:
        return BLOCKED
    
    return EXECUTED
```

### 3. Policy Engine (manager)
**Technology:** YAML configuration  
**Purpose:** Centralized governance rules

**Configuration Structure:**
```yaml
policies:
  - tool: "execute_payment"
    action: "ALLOW"
    anyOf:
      # Verified merchants: up to ₹50,000
      - allOf:
          - field: "recipient_type"
            condition: "EQUALS"
            value: "VERIFIED_MERCHANT"
          - field: "amount"
            condition: "LESS_THAN_OR_EQUAL"
            value: 50000
      
      # Unverified vendors: up to ₹5,000
      - allOf:
          - field: "recipient_type"
            condition: "EQUALS"
            value: "UNVERIFIED"
          - field: "amount"
            condition: "LESS_THAN_OR_EQUAL"
            value: 5000
```

## Data Flow

### Example: "Pay my electricity bill"

**Step 1: Frontend Request**
```javascript
fetch('http://localhost:5001/api/execute', {
  method: 'POST',
  body: JSON.stringify({ text: "Pay my electricity bill" })
})
```

**Step 2: Backend Processing**
```python
# Extract intent
merchant = 'ELECTRICITY_BOARD'
amount = 6200

# Evaluate policy
policy_result = evaluate_payment_policy(amount, merchant)
# Result: BLOCKED (6200 > 5000)

# Build execution trace
trace = {
  "stages": [
    {"type": "USER_INPUT", ...},
    {"type": "REASONING", ...},
    {"type": "PLAN", ...},
    {"type": "INTENT_TOKEN", "payload": {"amount": 6200, ...}},
    {"type": "POLICY_EVALUATION", "payload": {"checks": [
      {"rule": "MERCHANT_ALLOWLIST", "result": "PASS"},
      {"rule": "MAX_TRANSACTION_AMOUNT", "result": "FAIL", "expected": "≤ 5000", "actual": 6200}
    ]}},
    {"type": "MCP_OUTCOME", "payload": {"status": "BLOCKED", "reason": "MAX_TRANSACTION_AMOUNT"}}
  ]
}
```

**Step 3: Frontend Display**
- Renders 6 stages sequentially
- POLICY_EVALUATION shows table with PASS/FAIL per rule
- MCP_OUTCOME displays BLOCKED in red with reason

## Integration Points

### Frontend → Backend
**Connection:** HTTP REST API  
**Format:** JSON

```javascript
// demo-ui/src/App.jsx
const handleRun = async () => {
  const response = await fetch('http://localhost:5001/api/execute', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: inputValue })
  });
  
  const data = await response.json();
  setVisibleStages(data.stages);
};
```

### Backend → Policy Engine
**Connection:** File system (YAML)  
**Format:** YAML configuration

```python
# api/server.py
def load_policy():
    policy_path = '../manager/policy_travel.yaml'
    with open(policy_path, 'r') as f:
        return yaml.safe_load(f)

POLICY = load_policy()
```

## Running the Integrated System

### Method 1: Automated Startup (Recommended)
```batch
# Windows
start_all.bat

# This launches both:
# - Backend API (http://localhost:5001)
# - Frontend UI (http://localhost:5174)
```

### Method 2: Manual Startup

**Terminal 1 - Backend:**
```bash
cd api
pip install -r requirements.txt
python server.py
```

**Terminal 2 - Frontend:**
```bash
cd demo-ui
npm install
npm run dev
```

### Method 3: Individual Services

**Backend only:**
```bash
cd api && python server.py
```

**Frontend only:**
```bash
cd demo-ui && npm run dev
```

## Testing the Integration

### 1. Health Check
```bash
curl http://localhost:5001/api/health
# Expected: {"status": "healthy", "service": "armouriq-api"}
```

### 2. Get Policy
```bash
curl http://localhost:5001/api/policy
# Expected: Full YAML policy configuration
```

### 3. Execute Transaction
```bash
curl -X POST http://localhost:5001/api/execute \
  -H "Content-Type: application/json" \
  -d '{"text": "Pay my electricity bill"}'
  
# Expected: Full execution trace with 6 stages
```

### 4. Frontend Test
1. Open http://localhost:5174
2. Enter "Pay my electricity bill"
3. Click "Propose Execution"
4. Verify stages appear with BLOCKED outcome

## Fallback Behavior

**If API is unavailable:**
- Frontend displays error message: "Using mock data (API unavailable)"
- Falls back to hardcoded `executionTrace` in App.jsx
- All UI features work with static data
- No break in demo experience

**Code:**
```javascript
try {
  const response = await fetch('http://localhost:5001/api/execute', ...);
  setVisibleStages(data.stages);
} catch (err) {
  setError('Using mock data (API unavailable)');
  setVisibleStages(executionTrace.stages); // Fallback
}
```

## Extending the System

### Adding New Transaction Types

**1. Update Policy (manager/policy_travel.yaml):**
```yaml
- tool: "execute_payment"
  action: "ALLOW"
  anyOf:
    - field: "merchant"
      condition: "EQUALS"
      value: "GAS_UTILITY"
```

**2. Update Backend (api/server.py):**
```python
if 'gas' in user_input.lower():
    merchant = 'GAS_UTILITY'
```

**3. Frontend automatically adapts:**
- No changes needed (renders any merchant name)

### Adding New Policy Rules

**1. Define in YAML:**
```yaml
- field: "transaction_frequency"
  condition: "LESS_THAN"
  value: 5  # Max 5 transactions per day
```

**2. Implement in Backend:**
```python
frequency_check = {
    'rule': 'TRANSACTION_FREQUENCY',
    'result': 'PASS' if daily_count < 5 else 'FAIL'
}
checks.append(frequency_check)
```

**3. Frontend displays automatically:**
- New row appears in POLICY_EVALUATION table

## Troubleshooting

**Problem:** Frontend shows "API unavailable"  
**Solution:** Ensure backend is running on port 5001

**Problem:** Backend returns 500 error  
**Solution:** Check policy YAML syntax and file path

**Problem:** Policy changes not reflected  
**Solution:** Restart backend (it loads policy on startup)

**Problem:** CORS errors in browser  
**Solution:** Backend has `flask-cors` enabled; check browser console

## Security Considerations

1. **Frontend is passive** - Cannot bypass policies
2. **Backend enforces rules** - Single source of truth
3. **Policy is file-based** - Easy to audit and version control
4. **HMAC tokens** - Intent verification (future integration)
5. **Audit logging** - All requests logged with timestamps

## Production Deployment

### Backend
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5001 api.server:app
```

### Frontend
```bash
cd demo-ui
npm run build
# Serve dist/ folder with nginx or CDN
```

### Environment Variables
```bash
export PORT=5001
export ARMOR_IQ_SECRET="production-secret-key"
export POLICY_PATH="/etc/armouriq/policy.yaml"
```

## Demo Script for Judges

1. **Show architecture diagram** (README.md)
2. **Open frontend** (http://localhost:5174)
3. **Explain context strip** (user, policy, MCP mode)
4. **Run default request** ("Pay my electricity bill")
5. **Walk through 6 stages**:
   - USER_INPUT: natural language
   - REASONING: non-binding analysis
   - PLAN: structured steps
   - INTENT_TOKEN: marked as UNTRUSTED (₹6,200)
   - POLICY_EVALUATION: table shows FAIL on amount limit
   - MCP_OUTCOME: BLOCKED with reason
6. **Show policy file** (manager/policy_travel.yaml)
7. **Demonstrate editing policy** (change limit to ₹10,000)
8. **Restart backend and rerun** - now shows EXECUTED
9. **Emphasize**: Frontend cannot bypass, backend enforces

## Questions?

See main README.md or check API documentation at http://localhost:5001/api/health

# ClaudiusMaximus - ArmourIQ Policy Enforcement System

A security-first agentic AI system with policy-enforced execution monitoring and visualization.

## Architecture

```
┌─────────────────┐
│   Frontend UI   │  (React - Port 5174)
│  demo-ui/       │  Visualization & User Interface
└────────┬────────┘
         │ HTTP API
         ▼
┌─────────────────┐
│   Backend API   │  (Flask - Port 5001)
│   api/          │  Policy Evaluation & Trace Generation
└────────┬────────┘
         │ Reads Policy
         ▼
┌─────────────────┐
│  Policy Engine  │  (YAML Configuration)
│  manager/       │  Governance Rules & Constraints
└─────────────────┘
```

## Quick Start

### Step 1: Clone Repository
```bash
git clone https://github.com/denverzuzarte/ClaudiusMaximus.git
cd ClaudiusMaximus
```

### Step 2: Configure Environment
```bash
cp sample_config.env config.env
# Edit config.env with your settings
```

### Step 3: Start Backend API Server
```bash
cd api
pip install -r requirements.txt
python server.py
```

Backend will start on `http://localhost:5001`

### Step 4: Start Frontend UI
```bash
cd demo-ui
npm install
npm run dev
```

Frontend will start on `http://localhost:5174`

## System Components

### 1. Frontend (`demo-ui/`)
Enterprise-grade React UI for visualizing policy-enforced execution traces.

**Features:**
- Context-aware interface (user, policy profile, MCP mode)
- Real-time execution monitoring
- 6-stage execution visualization
- Professional, compliance-oriented design

### 2. Backend API (`api/`)
Flask REST API that bridges frontend and policy engine.

**Endpoints:**
- `POST /api/execute` - Submit execution request
- `GET /api/policy` - Get current policy configuration
- `GET /api/health` - Health check

### 3. Policy Engine (`manager/`)
YAML-based governance rules and constraints.

**Configuration:**
- Transaction limits
- Merchant allowlists
- Violation handling (BLOCK vs REQUIRE_HUMAN_APPROVAL)

### 4. MCP Server (`executor/`)
FastMCP server for tool execution (currently: flight booking, can be extended).

## Execution Flow

1. **USER_INPUT** - Natural language request
2. **REASONING** - Non-binding LLM analysis
3. **PLAN** - Structured planning steps
4. **INTENT_TOKEN** - Narrowed, executable proposal (UNTRUSTED)
5. **POLICY_EVALUATION** - Authoritative rule checks
6. **MCP_OUTCOME** - Final execution result (EXECUTED or BLOCKED)

## Development

### Running Individual Components

**Backend API:**
```bash
cd api
python server.py
```

**Frontend:**
```bash
cd demo-ui
npm run dev
```

**MCP Server:**
```bash
cd executor
python server.py
```

### Configuration Files

- `config.env` - Environment variables
- `manager/policy_travel.yaml` - Policy configuration
- `mcp.json` - MCP server configuration

## Integration Notes

- Frontend calls Backend API for execution requests
- Backend evaluates requests against policy rules
- Falls back to mock data if API unavailable
- All execution traces are logged and visualized

## Production Deployment

1. Set proper environment variables in `config.env`
2. Use production WSGI server (gunicorn) for API
3. Build frontend: `cd demo-ui && npm run build`
4. Configure reverse proxy (nginx) for serving static files
5. Enable HTTPS/TLS for all connections

## Security Features

- HMAC-based intent token verification
- Policy-enforced execution constraints
- Audit logging for all requests
- Separation of concerns (frontend cannot bypass policies)

## License

See LICENSE file for details.
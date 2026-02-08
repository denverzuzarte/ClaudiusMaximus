# ArmourIQ API Server

Backend API server that bridges the frontend UI with the MCP execution layer.

## Features

- REST API for execution requests
- Policy evaluation engine
- Execution trace generation
- YAML-based policy configuration

## Installation

```bash
cd api
pip install -r requirements.txt
```

## Running the Server

```bash
python server.py
```

The server will start on `http://localhost:5001`

## API Endpoints

### POST /api/execute
Execute a transaction request with policy enforcement.

**Request:**
```json
{
  "text": "Pay my electricity bill"
}
```

**Response:**
```json
{
  "stages": [...],
  "timestamp": "2026-02-07T14:30:00Z",
  "execution_id": "exec_1234567890"
}
```

### GET /api/policy
Get current policy configuration.

### GET /api/health
Health check endpoint.

## Environment Variables

- `PORT`: Server port (default: 5001)
- `ARMOR_IQ_SECRET`: Secret key for HMAC token generation

## Integration with Frontend

The frontend (`demo-ui`) connects to this API to:
1. Submit execution requests
2. Receive real-time execution traces
3. Display policy evaluation results

Falls back to mock data if API is unavailable.

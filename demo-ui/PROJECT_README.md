# Security-First Agentic AI Demo UI

A React-based visualization interface for demonstrating policy-enforced agentic workflow execution.

## Overview

This demo UI visualizes the backend execution of an agentic AI system with built-in security policies. The frontend is a **passive observer** that renders execution stages exactly as emitted by the backend.

## Execution Flow

The system processes requests through 6 distinct stages:

1. **USER_INPUT** - Natural language user request
2. **REASONING** - Non-binding LLM reasoning (Gray)
3. **PLAN** - Structured planning steps (Purple)
4. **INTENT_TOKEN** - Narrowed, executable proposal marked as UNTRUSTED (Blue)
5. **POLICY_EVALUATION** - Authoritative rule checks (Yellow)
6. **MCP_OUTCOME** - Final execution result (Red for blocked, Green for executed)

## Key Design Principles

- **Frontend is Passive**: The UI does NOT infer, compute, or enforce any logic
- **Backend-Driven**: All stages are emitted by the backend and rendered as-is
- **Visual Clarity**: Color semantics make safety and enforcement obvious to judges
- **Demo-Ready**: Clean, minimal design optimized for presentation

## Project Structure

```
demo-ui/
├── src/
│   ├── components/
│   │   ├── StageCard.jsx      # Individual stage rendering component
│   │   └── StageCard.css      # Stage-specific styling with color semantics
│   ├── App.jsx                 # Main application with execution trace
│   ├── App.css                 # Application-wide styling
│   └── index.css               # Base CSS reset and typography
├── package.json
└── vite.config.js
```

## Running the Demo

```bash
# Install dependencies (already done)
npm install

# Start development server
npm run dev
```

The app will be available at `http://localhost:5174/` (or next available port).

## Usage

1. Enter a request in the text input (default: "Pay my electricity bill")
2. Click **Run** to visualize the execution trace
3. Stages appear sequentially with staggered animation
4. Click **Reset** to clear and try again

## Color Semantics

| Color  | Stage Type | Meaning |
|--------|-----------|---------|
| Gray   | REASONING | Non-binding thought process |
| Purple | PLAN | Structured planning steps |
| Blue   | INTENT_TOKEN | UNTRUSTED proposal |
| Yellow | POLICY_EVALUATION | AUTHORITATIVE checks |
| Red    | MCP_OUTCOME (BLOCKED) | Security policy violation |
| Green  | MCP_OUTCOME (EXECUTED) | Successful execution |

## Mock Data

The current implementation uses hardcoded execution trace data that demonstrates a **blocked transaction** scenario:
- User requests to pay electricity bill (₹6,200)
- Policy check fails: `MAX_TRANSACTION_AMOUNT` (limit: ₹5,000)
- Transaction is blocked by the system

## Tech Stack

- **React 18** - UI library
- **Vite** - Build tool and dev server
- **Plain CSS** - Styling with semantic color coding

## Notes for Judges

- This UI demonstrates **security-first design** where policies are enforced at the infrastructure level
- The frontend cannot bypass or override policy decisions
- All business logic and security enforcement happens on the backend
- Visual distinction between untrusted intents and authoritative policy checks is intentional

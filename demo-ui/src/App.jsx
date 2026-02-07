import React, { useState } from 'react';
import StageCard from './components/StageCard';
import './App.css';

const executionTrace = {
  stages: [
    {
      type: "USER_INPUT",
      payload: { text: "Pay my electricity bill" }
    },
    {
      type: "REASONING",
      payload: {
        text: "The user wants to pay a recurring utility bill. I should identify the merchant, estimate the amount, and propose a payment."
      }
    },
    {
      type: "PLAN",
      payload: {
        steps: [
          "Identify electricity provider",
          "Retrieve last bill amount",
          "Propose a payment intent"
        ]
      }
    },
    {
      type: "INTENT_TOKEN",
      payload: {
        action: "PAY_BILL",
        amount: 6200,
        merchant: "ELECTRICITY_BOARD",
        confidence: 0.91
      }
    },
    {
      type: "POLICY_EVALUATION",
      payload: {
        checks: [
          { rule: "MERCHANT_ALLOWLIST", result: "PASS" },
          {
            rule: "MAX_TRANSACTION_AMOUNT",
            result: "FAIL",
            expected: "≤ 5000",
            actual: 6200
          }
        ]
      }
    },
    {
      type: "MCP_OUTCOME",
      payload: {
        status: "BLOCKED",
        reason: "MAX_TRANSACTION_AMOUNT"
      }
    }
  ]
};

function App() {
  const [inputValue, setInputValue] = useState('Pay my electricity bill');
  const [showExecution, setShowExecution] = useState(false);
  const [visibleStages, setVisibleStages] = useState([]);

  const handleRun = () => {
    setShowExecution(true);
    setVisibleStages(executionTrace.stages);
  };

  const handleReset = () => {
    setShowExecution(false);
    setVisibleStages([]);
  };

  return (
    <div className="app">
      <header className="header">
        <div className="header-content">
          <div className="header-left">
            <div className="logo">ARMOURIQ</div>
            <div className="header-title">Policy Enforcement Monitor</div>
          </div>
        </div>
      </header>

      <div className="context-strip">
        <div className="context-strip-content">
          <div className="context-item">
            <span className="context-label">Active User</span>
            <span className="context-value">admin@armouriq.internal</span>
          </div>
          <div className="context-divider"></div>
          <div className="context-item">
            <span className="context-label">Policy Profile</span>
            <span className="context-value">STANDARD_TRANSACTION</span>
          </div>
          <div className="context-divider"></div>
          <div className="context-item">
            <span className="context-label">MCP Mode</span>
            <span className="context-value status-enforced">ENFORCED</span>
          </div>
        </div>
      </div>

      <div className="container">
        {!showExecution && (
          <div className="guidance-section">
            <p className="guidance-text">
              The system will analyze intent, generate a constrained plan, enforce policies, and then execute or block based on governance rules.
            </p>
          </div>
        )}

        <div className="input-section">
          <label className="input-label">TRANSACTION REQUEST</label>
          <div className="input-row">
            <input
              type="text"
              className="input-field"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Enter transaction request"
              disabled={showExecution}
            />
            <button 
              className="run-button" 
              onClick={showExecution ? handleReset : handleRun}
            >
              {showExecution ? 'Reset Session' : 'Propose Execution'}
            </button>
          </div>
          <p className="disclaimer-text">
            All requests are subject to policy enforcement. Execution is not guaranteed.
          </p>
        </div>

        {showExecution && (
          <div className="execution-flow">
            <div className="flow-header">
              <div className="flow-title">Execution Log</div>
              <div className="flow-timestamp">{new Date().toISOString().replace('T', ' ').substring(0, 19)} UTC</div>
            </div>
            
            <div className="stages-container">
              {visibleStages.map((stage, index) => (
                <StageCard key={index} stage={stage} index={index} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;

import React, { useState } from 'react';
import StageCard from './components/StageCard';
import QuestionnaireModal from './components/QuestionnaireModal';
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [executionId, setExecutionId] = useState(null);
  const [showQuestionnaire, setShowQuestionnaire] = useState(false);
  const [questions, setQuestions] = useState([]);
  const [originalRequest, setOriginalRequest] = useState('');

  const handleRun = async () => {
    setShowExecution(true);
    setLoading(true);
    setError(null);
    setVisibleStages([]);
    setOriginalRequest(inputValue);
    
    try {
      // Call the backend API with intent processing
      const response = await fetch('http://localhost:5001/api/execute-with-intent', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: inputValue
        })
      });
      
      if (!response.ok) {
        throw new Error('Failed to execute request');
      }
      
      const data = await response.json();
      
      // Check if we need to ask questions
      if (data.needs_questions) {
        setQuestions(data.questions);
        setShowQuestionnaire(true);
        setLoading(false);
      } else {
        // Direct execution (questions already answered)
        setExecutionId(data.execution_id);
        setVisibleStages(data.stages);
        setLoading(false);
      }
    } catch (err) {
      console.error('API Error:', err);
      // Fallback to mock data if API fails
      setError('Using mock data (API unavailable)');
      setVisibleStages(executionTrace.stages);
      setLoading(false);
    }
  };

  const handleQuestionnaireSubmit = async (answers) => {
    setShowQuestionnaire(false);
    setLoading(true);
    
    try {
      // Answers already formatted by QuestionnaireModal with id, answer, field, etc.
      // No need to reformat - just pass them through
      
      // Call API with user responses
      const response = await fetch('http://localhost:5001/api/execute-with-intent', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: originalRequest,
          responses: answers  // Pass answers directly without reformatting
        })
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to execute request');
      }
      
      setExecutionId(data.execution_id);
      setVisibleStages(data.stages);
    } catch (err) {
      console.error('API Error:', err);
      setError(err.message || 'Failed to process answers');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setShowExecution(false);
    setVisibleStages([]);
    setError(null);
    setExecutionId(null);
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
              disabled={showExecution || loading}
            />
            <button 
              className="run-button" 
              onClick={showExecution ? handleReset : handleRun}
              disabled={loading}
            >
              {loading ? 'Processing...' : (showExecution ? 'Reset Session' : 'Propose Execution')}
            </button>
          </div>
          <p className="disclaimer-text">
            All requests are subject to policy enforcement. Execution is not guaranteed.
          </p>
          {error && (
            <p className="error-text">
              {error}
            </p>
          )}
        </div>

        {showExecution && (
          <div className="execution-flow">
            <div className="flow-header">
              <div className="flow-title">Execution Log</div>
              <div className="flow-meta">
                {executionId && (
                  <span className="execution-id">ID: {executionId}</span>
                )}
                <div className="flow-timestamp">{new Date().toISOString().replace('T', ' ').substring(0, 19)} UTC</div>
              </div>
            </div>
            
            <div className="stages-container">
              {visibleStages.map((stage, index) => (
                <StageCard key={index} stage={stage} index={index} />
              ))}
            </div>
          </div>
        )}
      </div>

      {showQuestionnaire && (
        <QuestionnaireModal
          questions={questions}
          onSubmit={handleQuestionnaireSubmit}
          onClose={() => {
            setShowQuestionnaire(false);
            setShowExecution(false);
            setLoading(false);
          }}
        />
      )}
    </div>
  );
}

export default App;

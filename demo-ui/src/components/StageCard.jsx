import React from 'react';
import './StageCard.css';

const StageCard = ({ stage, index }) => {
  const renderPayload = () => {
    switch (stage.type) {
      case 'USER_INPUT':
        return (
          <div className="payload">
            <p className="user-input-text">{stage.payload.text}</p>
          </div>
        );

      case 'REASONING':
        return (
          <div className="payload">
            <div className="stage-label">Non-binding analysis</div>
            <p className="reasoning-text">{stage.payload.text}</p>
          </div>
        );

      case 'PLAN':
        return (
          <div className="payload">
            <ul className="plan-steps">
              {stage.payload.steps.map((step, idx) => (
                <li key={idx}>{step}</li>
              ))}
            </ul>
          </div>
        );

      case 'INTENT_TOKEN':
        return (
          <div className="payload">
            <div className="intent-badge">UNTRUSTED</div>
            <table className="intent-table">
              <tbody>
                <tr>
                  <td className="label">Action</td>
                  <td className="value">{stage.payload.action}</td>
                </tr>
                <tr>
                  <td className="label">Amount</td>
                  <td className="value">₹{stage.payload.amount.toLocaleString()}</td>
                </tr>
                <tr>
                  <td className="label">Merchant</td>
                  <td className="value">{stage.payload.merchant}</td>
                </tr>
                <tr>
                  <td className="label">Confidence</td>
                  <td className="value">{(stage.payload.confidence * 100).toFixed(0)}%</td>
                </tr>
              </tbody>
            </table>
          </div>
        );

      case 'POLICY_EVALUATION':
        return (
          <div className="payload">
            <div className="policy-badge">AUTHORITATIVE</div>
            <table className="checks-table">
              <thead>
                <tr>
                  <th>Policy Rule</th>
                  <th>Result</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {stage.payload.checks.map((check, idx) => (
                  <tr key={idx} className={check.result.toLowerCase()}>
                    <td className="check-rule">{check.rule}</td>
                    <td className="check-result">
                      <span className={`result-badge ${check.result.toLowerCase()}`}>
                        {check.result}
                      </span>
                    </td>
                    <td className="check-details">
                      {check.expected ? (
                        <span>Expected {check.expected}, Actual {check.actual}</span>
                      ) : (
                        <span>—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );

      case 'MCP_OUTCOME':
        return (
          <div className="payload">
            <div className={`outcome-status ${stage.payload.status.toLowerCase()}`}>
              <span className="outcome-label">STATUS</span>
              <span className="outcome-value">{stage.payload.status}</span>
            </div>
            {stage.payload.reason && (
              <div className="outcome-reason">
                <span className="label">Enforcement Reason</span>
                <span className="value">{stage.payload.reason}</span>
              </div>
            )}
          </div>
        );

      default:
        return <div className="payload">{JSON.stringify(stage.payload)}</div>;
    }
  };

  return (
    <div className={`stage-card ${stage.type.toLowerCase()}`}>
      <div className="stage-header">
        <div className="stage-number">STAGE {index + 1}</div>
        <div className="stage-title">{stage.type.replace(/_/g, ' ')}</div>
      </div>
      <div className="stage-content">
        {renderPayload()}
      </div>
    </div>
  );
};

export default StageCard;

import React, { useEffect, useState } from 'react';
import './StageCard.css';

const StageCard = ({ stage, index }) => {
  const [hasScrolledToBottom, setHasScrolledToBottom] = useState(false);

  // Auto-redirect to payment gateway when APPROVED and user scrolls to bottom
  useEffect(() => {
    if (stage.type === 'MCP_OUTCOME' && 
        stage.payload.status === 'APPROVED' && 
        stage.payload.payment_url) {
      
      const checkScrollPosition = () => {
        const scrollHeight = document.documentElement.scrollHeight;
        const scrollTop = document.documentElement.scrollTop || document.body.scrollTop;
        const clientHeight = document.documentElement.clientHeight;
        
        // Check if user is within 150px of the bottom
        if (scrollHeight - scrollTop - clientHeight < 150) {
          setHasScrolledToBottom(true);
        }
      };

      // Check immediately in case page is short enough to not need scrolling
      checkScrollPosition();
      
      // Add scroll listener
      window.addEventListener('scroll', checkScrollPosition);
      
      return () => {
        window.removeEventListener('scroll', checkScrollPosition);
      };
    }
  }, [stage]);

  // Trigger redirect when scrolled to bottom
  useEffect(() => {
    if (hasScrolledToBottom && 
        stage.type === 'MCP_OUTCOME' && 
        stage.payload.status === 'APPROVED' && 
        stage.payload.payment_url) {
      // Small delay after reaching bottom
      const timer = setTimeout(() => {
        window.location.href = stage.payload.payment_url;
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [hasScrolledToBottom, stage]);
  
  // Convert basic markdown to HTML
  const formatMarkdown = (text) => {
    if (!text) return '';
    
    let formatted = text;
    
    // Handle proper markdown bold: **text**
    formatted = formatted.replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>');
    
    // Handle emphasis/labels with colons: "text:**" -> make it a label
    formatted = formatted.replace(/([A-Za-z0-9\s]+):\*\*/g, '<strong>$1:</strong>');
    
    // Handle orphaned ** at the end of words (remove them)
    formatted = formatted.replace(/([a-zA-Z])\*\*(?!\*)/g, '$1');
    
    // Handle markdown bold with underscores: __text__
    formatted = formatted.replace(/__([^_]+?)__/g, '<strong>$1</strong>');
    
    // Handle proper markdown italic: *text* (but not **)
    formatted = formatted.replace(/(?<!\*)\*([^*]+?)\*(?!\*)/g, '<em>$1</em>');
    
    // Handle italic with underscores: _text_
    formatted = formatted.replace(/(?<!_)_([^_]+?)_(?!_)/g, '<em>$1</em>');
    
    // Clean up any remaining stray ** or *
    formatted = formatted.replace(/\*\*/g, '');
    formatted = formatted.replace(/\s\*\s/g, ' ');
    
    // Handle line breaks
    formatted = formatted.replace(/\n/g, '<br />');
    
    return formatted;
  };

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
            <div 
              className="reasoning-text" 
              dangerouslySetInnerHTML={{ __html: formatMarkdown(stage.payload.text) }}
            />
          </div>
        );

      case 'PLAN':
        return (
          <div className="payload">
            <ul className="plan-steps">
              {stage.payload.steps.map((step, idx) => (
                <li 
                  key={idx}
                  dangerouslySetInnerHTML={{ __html: formatMarkdown(step) }}
                />
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
                {stage.payload.amount !== undefined ? (
                  <>
                    <tr>
                      <td className="label">Amount</td>
                      <td className="value">₹{stage.payload.amount.toLocaleString()}</td>
                    </tr>
                    <tr>
                      <td className="label">Merchant</td>
                      <td className="value">{stage.payload.merchant}</td>
                    </tr>
                  </>
                ) : (
                  <>
                    <tr>
                      <td className="label">Total Steps</td>
                      <td className="value">{stage.payload.steps}</td>
                    </tr>
                    <tr>
                      <td className="label">Complete</td>
                      <td className="value">{stage.payload.complete_steps} / {stage.payload.steps}</td>
                    </tr>
                  </>
                )}
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
            <div className="checks-list">
              {stage.payload.checks.map((check, idx) => (
                <div key={idx} className={`check-item ${check.result.toLowerCase()}`}>
                  <div className="check-header">
                    <span className="check-title">{check.rule}</span>
                    <span className={`result-badge ${check.result.toLowerCase()}`}>
                      {check.result}
                    </span>
                  </div>
                  {check.description && (
                    <div className="check-description">{check.description}</div>
                  )}
                  {check.result === 'FAIL' && check.actual && (
                    <div className="check-failure">
                      <strong>Issue:</strong> {check.actual}
                    </div>
                  )}
                  {check.reason && (
                    <div className="check-reason">
                      {check.reason}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        );

      case 'BOOKING_APPROVAL':
        const details = stage.payload.details || {};
        return (
          <div className="payload">
            <div className="booking-status awaiting">
              <span className="status-label">⏳ AWAITING CONFIRMATION</span>
            </div>
            
            <div className="booking-summary">
              <h4>AI Recommendation Summary</h4>
              <div className="booking-field">
                <strong>Hotel:</strong> {details.hotel_name}
              </div>
              <div className="booking-field">
                <strong>Address:</strong> {details.address}
              </div>
              <div className="booking-field">
                <strong>Check-in:</strong> {details.check_in}
              </div>
              <div className="booking-field">
                <strong>Check-out:</strong> {details.check_out}
              </div>
              <div className="booking-field">
                <strong>Price:</strong> {details.price}
              </div>
              <div className="booking-field">
                <strong>Booking Platform:</strong> {details.website}
              </div>
            </div>
            
            <div className="booking-actions">
              <button 
                className="btn-proceed"
                onClick={() => handleProceedToBook(stage.payload.execution_id, details)}
              >
                ✓ Proceed to Book
              </button>
              <button 
                className="btn-cancel"
                onClick={() => handleModifySearch()}
              >
                ✗ Modify Search
              </button>
            </div>
            
            <div className="booking-note">
              <small>By clicking "Proceed to Book", you'll be directed to {details.website} to complete your reservation.</small>
            </div>
          </div>
        );

      case 'MCP_OUTCOME':
        const status = stage.payload.status;
        const isApproved = status === 'APPROVED';
        const isBlocked = status === 'BLOCKED';
        const requiresApproval = status === 'REQUIRES_APPROVAL';
        
        return (
          <div className="payload">
            <div className={`outcome-status ${status.toLowerCase().replace('_', '-')}`}>
              <span className="outcome-label">STATUS</span>
              <span className="outcome-value">{status}</span>
            </div>
            
            {/* Triggered Rules Summary */}
            {stage.payload.triggered_rules && stage.payload.triggered_rules.length > 0 && (
              <div className="triggered-rules">
                <h4>⚖️ Triggered Policy Rules:</h4>
                <div className="rules-list">
                  {stage.payload.triggered_rules.map((rule, idx) => (
                    <span key={idx} className="rule-badge">{rule.replace(/_/g, ' ')}</span>
                  ))}
                </div>
              </div>
            )}
            
            {isApproved && stage.payload.payment_url && (
              <div className="payment-redirect">
                <div className="approval-summary">
                  <div className="approval-check">
                    <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
                      <circle cx="24" cy="24" r="22" fill="#10b981" fillOpacity="0.1" stroke="#10b981" strokeWidth="2"/>
                      <path d="M14 24l8 8 12-12" stroke="#10b981" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                  <div className="approval-text">
                    <h3>Request Validated Successfully</h3>
                    <p>All policy requirements satisfied with {Math.round((stage.payload.confidence || 0.94) * 100)}% verification confidence.</p>
                  </div>
                </div>
                <div className="redirect-message">
                  {!hasScrolledToBottom ? (
                    <>
                      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" className="scroll-icon">
                        <path d="M10 4v12m0 0l4-4m-4 4l-4-4" stroke="#6b7280" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                      <p>Scroll down to review details and proceed to payment</p>
                    </>
                  ) : (
                    <>
                      <div className="spinner"></div>
                      <p>Redirecting to secure payment gateway...</p>
                    </>
                  )}
                </div>
                <div className="payment-footer">
                  <div className="security-badge">
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                      <path d="M7 1L2 3v4c0 3 2.5 5.5 5 6 2.5-.5 5-3 5-6V3l-5-2z" stroke="#6b7280" fill="#f3f4f6" strokeWidth="1.5"/>
                      <path d="M5 7l1.5 1.5L10 5" stroke="#10b981" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    <span>PCI-DSS Compliant</span>
                  </div>
                  <span className="divider">•</span>
                  <div className="powered-by">
                    <span>Powered by</span>
                    <strong>ArmorIQ</strong>
                  </div>
                </div>
              </div>
            )}
            
            {/* Human Approval Required */}
            {requiresApproval && (
              <div className="approval-required">
                <div className="approval-header-main">
                  <svg width="18" height="18" viewBox="0 0 18 18" fill="none" className="warning-icon">
                    <path d="M9 1L17 16H1L9 1Z" stroke="#f59e0b" strokeWidth="2" fill="none" strokeLinejoin="round"/>
                    <path d="M9 7v3M9 12h.01" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round"/>
                  </svg>
                  <h4>Manual Approval Required</h4>
                </div>
                <p className="approval-description">The following items require management review before proceeding:</p>
                {stage.payload.failures && (
                  <div className="approval-list">
                    {stage.payload.failures.map((failure, idx) => (
                      <div key={idx} className={`approval-card severity-${failure.severity?.toLowerCase().replace(/_/g, '-')}`}>
                        <div className="approval-card-header">
                          <span className={`severity-badge ${failure.severity?.toLowerCase().replace(/_/g, '-')}`}>
                            REVIEW NEEDED
                          </span>
                          <span className="approval-category">{failure.category?.replace(/_/g, ' ')}</span>
                        </div>
                        <div className="approval-reason">{failure.reason}</div>
                      </div>
                    ))}
                  </div>
                )}
                {stage.payload.payment_url && (
                  <button 
                    className="btn-request-approval btn-approve-payment"
                    onClick={() => window.location.href = stage.payload.payment_url}
                  >
                    <span className="approval-price">{stage.payload.price || 'Approve & Pay'}</span>
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="arrow-icon">
                      <path d="M6 3l5 5-5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </button>
                )}
              </div>
            )}
            
            {/* Hard Block Failures */}
            {isBlocked && stage.payload.failures && (
              <div className="failure-details">
                <div className="failure-header-main">
                  <svg width="18" height="18" viewBox="0 0 18 18" fill="none" className="violation-icon">
                    <circle cx="9" cy="9" r="8" stroke="#dc2626" strokeWidth="2" fill="none"/>
                    <path d="M5 9L13 9" stroke="#dc2626" strokeWidth="2" strokeLinecap="round"/>
                  </svg>
                  <h4>Policy Violations</h4>
                </div>
                <div className="violations-grid">
                  {stage.payload.failures.map((failure, idx) => (
                    <div key={idx} className={`violation-card severity-${failure.severity?.toLowerCase().replace(/_/g, '-')}`}>
                      <div className="violation-header">
                        <span className={`severity-badge ${failure.severity?.toLowerCase().replace(/_/g, '-')}`}>
                          {failure.severity === 'BLOCK' ? 'BLOCKED' : 
                           failure.severity === 'BLOCK_AND_LOG' ? 'BLOCKED' : 
                           failure.severity === 'REQUIRE_HUMAN_APPROVAL' ? 'APPROVAL REQUIRED' : 'ERROR'}
                        </span>
                        <span className="violation-category">{failure.category?.replace(/_/g, ' ')}</span>
                      </div>
                      <div className="violation-reason">{failure.reason}</div>
                    </div>
                  ))}
                </div>
                <div className="policy-footer">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="info-icon">
                    <circle cx="8" cy="8" r="7" stroke="#6b7280" strokeWidth="1.5" fill="none"/>
                    <path d="M8 7v4M8 5h.01" stroke="#6b7280" strokeWidth="1.5" strokeLinecap="round"/>
                  </svg>
                  <span>Unable to proceed - policy constraints not satisfied</span>
                </div>
              </div>
            )}
            
            {stage.payload.reason && (
              <div className="outcome-reason">
                <span className="label">Reason Code</span>
                <span className="value">{stage.payload.reason}</span>
              </div>
            )}
          </div>
        );

      default:
        return <div className="payload">{JSON.stringify(stage.payload)}</div>;
    }
  };
  
  // Handler functions for booking actions
  const handleProceedToBook = async (executionId, details) => {
    try {
      // Call API to confirm booking
      const response = await fetch('http://localhost:5001/api/confirm-booking', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          execution_id: executionId,
          details: details
        })
      });
      
      const result = await response.json();
      
      if (result.success) {
        alert(`✅ Booking confirmed!\n\nYou'll be redirected to ${details.website} to complete payment.`);
        // In a real app, redirect to booking website
        // window.open(result.booking_url, '_blank');
      } else {
        alert('❌ Booking failed: ' + result.error);
      }
    } catch (error) {
      console.error('Booking error:', error);
      alert('❌ Error confirming booking. Please try again.');
    }
  };
  
  const handleModifySearch = () => {
    alert('Feature coming soon: Modify your search parameters');
    window.location.reload();  // For now, just reload to start over
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


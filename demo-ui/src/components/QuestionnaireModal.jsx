import React from 'react';
import './QuestionnaireModal.css';

const QuestionnaireModal = ({ questions, onSubmit, onClose }) => {
  const [answers, setAnswers] = React.useState({});
  const [currentQuestion, setCurrentQuestion] = React.useState(0);

  const handleAnswer = (questionId, answer) => {
    setAnswers(prev => ({
      ...prev,
      [questionId]: answer
    }));
  };

  const handleNext = () => {
    if (currentQuestion < questions.length - 1) {
      setCurrentQuestion(prev => prev + 1);
    }
  };

  const handlePrevious = () => {
    if (currentQuestion > 0) {
      setCurrentQuestion(prev => prev - 1);
    }
  };

  const handleSubmit = () => {
    const formattedAnswers = Object.entries(answers).map(([id, answer]) => {
      const question = questions.find(q => q.id === id);
      return {
        id,
        question: question?.question,
        answer,
        field: question?.field,
        step: question?.step
      };
    });
    onSubmit(formattedAnswers);
  };

  const currentQ = questions[currentQuestion];
  const currentAnswer = answers[currentQ?.id] || '';
  const progress = ((currentQuestion + 1) / questions.length) * 100;

  return (
    <div className="modal-overlay">
      <div className="modal-container">
        <div className="modal-header">
          <h2>Travel Information Form</h2>
          <button className="close-button" onClick={onClose} aria-label="Close">×</button>
        </div>

        <div className="progress-bar-container">
          <div className="progress-bar" style={{ width: `${progress}%` }}></div>
          <span className="progress-text">
            Question {currentQuestion + 1} of {questions.length}
          </span>
        </div>

        <div className="modal-body">
          {currentQ && (
            <>
              <div className="question-section">
                <div className="question-meta">
                  <span className="step-badge">Step {currentQ.step}</span>
                  <span className="field-badge">{currentQ.field}</span>
                </div>

                <h3 className="question-text">{currentQ.question}</h3>

                {currentQ.why_asking && (
                  <p className="question-description">{currentQ.why_asking}</p>
                )}
              </div>

              <div className="answer-section">
                <label className="answer-label">Your Response</label>
                <input
                  type="text"
                  className="answer-input"
                  value={currentAnswer !== 'yes' && currentAnswer !== 'no' ? currentAnswer : ''}
                  onChange={(e) => handleAnswer(currentQ.id, e.target.value)}
                  placeholder="Enter your response..."
                  autoFocus
                />
              </div>
            </>
          )}
        </div>

        <div className="modal-footer">
          <div className="navigation-buttons">
            <button
              className="nav-btn secondary"
              onClick={handlePrevious}
              disabled={currentQuestion === 0}
            >
              ← Previous
            </button>

            {currentQuestion < questions.length - 1 ? (
              <button
                className="nav-btn primary"
                onClick={handleNext}
                disabled={!currentAnswer}
              >
                Next →
              </button>
            ) : (
              <button
                className="nav-btn primary"
                onClick={handleSubmit}
                disabled={Object.keys(answers).length < questions.length}
              >
                Submit All Answers
              </button>
            )}
          </div>

          <div className="answers-summary">
            Answered: {Object.keys(answers).length} / {questions.length}
          </div>
        </div>
      </div>
    </div>
  );
};

export default QuestionnaireModal;

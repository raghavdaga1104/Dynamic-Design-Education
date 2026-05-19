// pages/Diagnostic.jsx
// ─────────────────────────────────────────────────────────────
// Placement test: user picks a topic → answers 10 questions →
// backend returns tier + starting_unit → redirect to dashboard.
// ─────────────────────────────────────────────────────────────

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { diagnostic as diagApi } from '../services/api';
import { Button, Spinner, Alert, Badge, ProgressBar } from '../components/ui';
import { domainIcon, domainColor } from '../utils/helpers';

const STEP = { PICK_TOPIC: 'pick_topic', QUIZ: 'quiz', RESULT: 'result' };

export default function DiagnosticPage() {
  const { userId, markDiagnosticDone } = useApp();
  const navigate = useNavigate();

  const [step, setStep]       = useState(STEP.PICK_TOPIC);
  const [topics, setTopics]   = useState([]);
  const [topic, setTopic]     = useState('');
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({}); // { qId: idx }
  const [current, setCurrent] = useState(0);
  const [result, setResult]   = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  // Fetch available topics on mount
  useEffect(() => {
    diagApi.getTopics()
      .then(r => setTopics(r.topics))
      .catch(() => setError('Could not load topics. Is the backend running?'));
  }, []);

  async function handleStartDiagnostic() {
    setLoading(true);
    setError('');
    try {
      const data = await diagApi.start(userId, topic);
      setQuestions(data.questions);
      setAnswers({});
      setCurrent(0);
      setStep(STEP.QUIZ);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSkip() {
    setLoading(true);
    try {
      await diagApi.skip(userId, topic);
      markDiagnosticDone();
      navigate('/dashboard');
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function handleAnswer(qId, idx) {
    setAnswers(prev => ({ ...prev, [qId]: idx }));
  }

  function handleNext() {
    if (current < questions.length - 1) setCurrent(c => c + 1);
  }
  function handlePrev() {
    if (current > 0) setCurrent(c => c - 1);
  }

  async function handleSubmit() {
    if (Object.keys(answers).length < questions.length) {
      setError('Please answer all questions before submitting.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const data = await diagApi.submit(userId, topic, answers);
      setResult(data);
      setStep(STEP.RESULT);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const q = questions[current];
  const answeredCount = Object.keys(answers).length;

  // ── Topic Picker ─────────────────────────────────────────
  if (step === STEP.PICK_TOPIC) {
    return (
      <div className="page-centered diag-page">
        <div className="diag-header">
          <h1 className="page-title">Placement Test</h1>
          <p className="page-subtitle">
            Answer 10 questions so the AI can place you at the right starting point.
            Takes about 3–5 minutes.
          </p>
        </div>

        {error && <Alert type="error">{error}</Alert>}

        {topics.length === 0 && !error ? (
          <Spinner message="Loading topics…" />
        ) : (
          <div className="topic-grid">
            {topics.map(t => (
              <button
                key={t}
                className={`topic-card ${topic === t ? 'topic-selected' : ''}`}
                onClick={() => setTopic(t)}
                style={{ '--domain-color': domainColor(t) }}
              >
                <span className="topic-icon">{domainIcon(t)}</span>
                <span className="topic-name">{t}</span>
                {topic === t && <span className="topic-check">✓</span>}
              </button>
            ))}
          </div>
        )}

        <div className="diag-actions">
          <Button
            onClick={handleStartDiagnostic}
            disabled={!topic}
            loading={loading}
            size="lg"
          >
            Start Diagnostic →
          </Button>
          <Button
            variant="ghost"
            onClick={handleSkip}
            disabled={!topic}
            loading={loading}
          >
            Skip — Start from Beginning
          </Button>
        </div>
      </div>
    );
  }

  // ── Quiz ──────────────────────────────────────────────────
  if (step === STEP.QUIZ) {
    return (
      <div className="page-centered diag-page">
        <div className="quiz-header">
          <div className="quiz-meta">
            <Badge color={domainColor(topic)}>{domainIcon(topic)} {topic}</Badge>
            <span className="quiz-progress-text">
              {current + 1} / {questions.length}
            </span>
          </div>
          <ProgressBar
            value={answeredCount}
            max={questions.length}
            color="var(--accent)"
            showPercent={false}
          />
        </div>

        {q && (
          <div className="question-card">
            <div className="question-difficulty">
              <Badge color={q.difficulty === 'easy' ? '#10b981' : q.difficulty === 'medium' ? '#f59e0b' : '#ef4444'}>
                {q.difficulty}
              </Badge>
            </div>
            <p className="question-text">{q.text}</p>

            <div className="options-list">
              {q.options.map((opt, idx) => (
                <button
                  key={idx}
                  className={`option-btn ${answers[q.question_id] === idx ? 'option-selected' : ''}`}
                  onClick={() => handleAnswer(q.question_id, idx)}
                >
                  <span className="option-letter">{String.fromCharCode(65 + idx)}</span>
                  <span className="option-text">{opt}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {error && <Alert type="error">{error}</Alert>}

        <div className="quiz-nav">
          <Button variant="ghost" onClick={handlePrev} disabled={current === 0}>← Prev</Button>

          {current < questions.length - 1 ? (
            <Button
              onClick={handleNext}
              disabled={answers[q?.question_id] == null}
            >
              Next →
            </Button>
          ) : (
            <Button
              onClick={handleSubmit}
              loading={loading}
              disabled={answeredCount < questions.length}
            >
              Submit Quiz ✓
            </Button>
          )}
        </div>

        {/* Dot nav for quick question jumping */}
        <div className="dot-nav">
          {questions.map((qq, i) => (
            <button
              key={i}
              className={`dot ${i === current ? 'dot-current' : ''} ${answers[qq.question_id] != null ? 'dot-answered' : ''}`}
              onClick={() => setCurrent(i)}
            />
          ))}
        </div>
      </div>
    );
  }

  // ── Result ────────────────────────────────────────────────
  if (step === STEP.RESULT && result) {
    const tierColors = {
      beginner: '#64748b', developing: '#f59e0b',
      proficient: '#6366f1', expert: '#10b981',
    };
    const tierColor = tierColors[result.tier] || '#64748b';

    return (
      <div className="page-centered diag-page">
        <div className="result-card">
          <div className="result-header">
            <div className="result-tier" style={{ color: tierColor }}>
              {result.tier?.toUpperCase()}
            </div>
            <h2 className="result-title">Placement Complete</h2>
            <p className="result-message">{result.message}</p>
          </div>

          <div className="result-stats">
            <div className="stat-box">
              <div className="stat-num">{result.score}</div>
              <div className="stat-label">Score</div>
            </div>
            <div className="stat-box">
              <div className="stat-num">{result.percent?.toFixed(0)}%</div>
              <div className="stat-label">Percentage</div>
            </div>
            <div className="stat-box">
              <div className="stat-num" style={{ fontSize: '1rem' }}>{result.starting_unit_name}</div>
              <div className="stat-label">Starting Unit</div>
            </div>
          </div>

          <div className="result-breakdown">
            <h3>Question Breakdown</h3>
            <div className="breakdown-grid">
              {result.breakdown?.map(b => (
                <div key={b.question_id} className={`breakdown-item ${b.is_correct ? 'correct' : 'wrong'}`}>
                  <span className="breakdown-icon">{b.is_correct ? '✓' : '✕'}</span>
                  <span className="breakdown-q">{b.question_id}</span>
                  <span className="breakdown-pts">+{b.earned}pt</span>
                </div>
              ))}
            </div>
          </div>

          <Button
            size="lg"
            className="btn-full"
            onClick={() => {
              markDiagnosticDone();
              navigate('/dashboard');
            }}
          >
            Start Learning →
          </Button>
        </div>
      </div>
    );
  }

  return <Spinner message="Loading…" />;
}

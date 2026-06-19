// pages/Learn.jsx
// ─────────────────────────────────────────────────────────────
// The core learning loop:
// 1. Get MCTS recommendation → show unit card
// 2. Load & show NOTES for the unit           ← NEW
// 3. Fetch quiz questions → quiz flow with instant-feedback
// 4. Submit IRT quiz → show results
// 5. Check flashcard gate → redirect or continue
// ─────────────────────────────────────────────────────────────

import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import {
  recommend as recApi,
  curriculum as currApi,
  quiz as quizApi,
  flashcard as flashApi,
} from '../services/api';
import { Button, Card, Spinner, Badge, Alert, ProgressBar, toast } from '../components/ui';
import { domainIcon, domainColor, difficultyColor } from '../utils/helpers';
import ChatSidebar from '../components/chat/ChatSidebar';

const PHASE = {
  LOADING_REC: 'loading_rec',
  SHOW_UNIT:   'show_unit',
  NOTES:       'notes',
  LOADING_QS:  'loading_qs',
  QUIZ:        'quiz',
  SUBMITTING:  'submitting',
  RESULT:      'result',
  FLASHCARDS:  'flashcards',
  COMPLETE:    'complete',
};

export default function Learn() {
  const { userId, profile } = useApp();
  const navigate = useNavigate();
  const location = useLocation();

  const [phase,        setPhase]        = useState(PHASE.LOADING_REC);
  const [rec,          setRec]          = useState(null);
  const [unitNotes,    setUnitNotes]    = useState([]);
  const [notesLoading, setNotesLoading] = useState(false);
  const [simplifyNote, setSimplifyNote] = useState(null);
  const [questions,    setQuestions]    = useState([]);
  const [answers,      setAnswers]      = useState({});
  const [current,      setCurrent]      = useState(0);
  const [instantFB,    setInstantFB]    = useState(null);
  const [quizResult,   setQuizResult]   = useState(null);
  const [flashGate,    setFlashGate]    = useState(null);
  const [error,        setError]        = useState('');
  const [chatOpen,     setChatOpen]     = useState(false);
  const [quizLock,     setQuizLock]     = useState(null);
  const [lockTick,     setLockTick]     = useState(0);

  // SessionStorage key scoped per user — persists rec across refresh (Bug #2 fix)
  const REC_KEY = `learn_rec_${userId}`;

  const loadRecommendation = useCallback(async (forceNew = false) => {
    setPhase(PHASE.LOADING_REC);
    setError('');
    setUnitNotes([]);

    // Bug fix #2: restore cached rec on refresh instead of re-running MCTS
    if (!forceNew) {
      try {
        const cached = sessionStorage.getItem(REC_KEY);
        if (cached) {
          setRec(JSON.parse(cached));
          setQuizLock(null);
          setPhase(PHASE.SHOW_UNIT);
          return;
        }
      } catch { /* ignore */ }
    }

    try {
      const data = await recApi.getNext(userId, profile.degree, profile.year, profile.interest);
      if (data.status === 'curriculum_complete') {
        sessionStorage.removeItem(REC_KEY);
        setPhase(PHASE.COMPLETE);
        return;
      }
      sessionStorage.setItem(REC_KEY, JSON.stringify(data));
      setRec(data);
      setQuizLock(null);
      setPhase(PHASE.SHOW_UNIT);
    } catch (e) {
      if (e.status === 409 && e.detail?.code === 'REVIEWS_DUE') {
        setFlashGate(e.detail);
        setPhase(PHASE.FLASHCARDS);
      } else {
        setError('Could not get recommendation: ' + e.message);
        setPhase(PHASE.SHOW_UNIT);
      }
    }
  }, [userId, profile, REC_KEY]);

  useEffect(() => {
    if (!userId) { navigate('/'); return; }

    // Bug fix #3: SkillTree passes a specific unit via router state — use it directly
    const forcedUnit = location.state?.forcedUnit;
    if (forcedUnit) {
      window.history.replaceState({}, '');   // clear so refresh doesn't re-apply
      sessionStorage.setItem(REC_KEY, JSON.stringify(forcedUnit));
      setRec(forcedUnit);
      setQuizLock(null);
      setPhase(PHASE.SHOW_UNIT);
      return;
    }

    loadRecommendation();
  }, [userId]); // eslint-disable-line

  // Countdown ticker — re-renders every second while lock is active
  useEffect(() => {
    if (!quizLock?.locked_until) return;
    const interval = setInterval(() => setLockTick(t => t + 1), 1000);
    return () => clearInterval(interval);
  }, [quizLock?.locked_until]);

  function secondsRemaining() {
    if (!quizLock?.locked_until) return 0;
    return Math.max(0, Math.floor(quizLock.locked_until - Date.now() / 1000));
  }

  function formatCountdown(secs) {
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = secs % 60;
    return `${h}h ${String(m).padStart(2, '0')}m ${String(s).padStart(2, '0')}s`;
  }

  // ── Load notes then enter NOTES phase ─────────────────────
  async function handleViewNotes() {
    setNotesLoading(true);
    setError('');
    try {
      const data = await currApi.getNotes(rec.unit_id);

      // New format: backend returns { topics: [{topic, definition, key_concepts, ...}] }
      if (data.topics?.length > 0) {
        setUnitNotes(data.topics.map(t => ({ topic: t.topic, items: [t] })));
      } else {
        // Legacy format: { notes: [{id, topic, concept, code, input_output, explanation}] }
        const notes = data.notes || [];
        const grouped = {};
        for (const note of notes) {
          const topic = note.topic || 'General';
          if (!grouped[topic]) grouped[topic] = [];
          grouped[topic].push(note);
        }
        setUnitNotes(Object.entries(grouped).map(([topic, items]) => ({ topic, items })));
      }

      setSimplifyNote(null);
      setChatOpen(false);
      setPhase(PHASE.NOTES);
    } catch {
      await handleStartQuiz();
    } finally {
      setNotesLoading(false);
    }
  }

  async function handleStartQuiz() {
    setPhase(PHASE.LOADING_QS);
    setError('');
    setQuizLock(null);
    try {
      const data = await currApi.getQuestions(rec.unit_id, userId);
      // If quiz was taken in last 24hrs, backend returns lock info instead of questions
      if (data.locked_until && data.seconds_remaining > 0) {
        setQuizLock({ locked_until: data.locked_until, seconds_remaining: data.seconds_remaining });
        setPhase(PHASE.SHOW_UNIT);
        return;
      }
      setQuestions(data.questions);
      setAnswers({});
      setCurrent(0);
      setInstantFB(null);
      setPhase(PHASE.QUIZ);
    } catch (e) {
      setError('Could not load questions: ' + e.message);
      setPhase(PHASE.SHOW_UNIT);
    }
  }

  function handleAnswer(qId, idx) {
    setAnswers(prev => ({ ...prev, [qId]: idx }));
    setInstantFB(null);
  }

  async function handleCheckAnswer() {
    const q = questions[current];
    const chosen = answers[q.question_id];
    if (chosen == null) return;
    try {
      const fb = await currApi.checkAnswer(rec.unit_id, q.question_id, chosen);
      setInstantFB(fb);
    } catch { /* silent */ }
  }

  function handleNext() {
    setInstantFB(null);
    setCurrent(c => Math.min(c + 1, questions.length - 1));
  }

  async function handleSubmitQuiz() {
    if (Object.keys(answers).length < questions.length) {
      toast('Please answer all questions first.', 'warning');
      return;
    }
    setPhase(PHASE.SUBMITTING);
    try {
      const result = await quizApi.submitIRT(userId, rec.unit_id, answers);
      setQuizResult(result);
      setPhase(PHASE.RESULT);
    } catch (e) {
      if (e.status === 423) {
        const detail = e.detail || {};
        setQuizLock({
          locked_until:      detail.locked_until || (Date.now() / 1000 + 86400),
          seconds_remaining: detail.seconds_remaining || 86400,
        });
        setPhase(PHASE.SHOW_UNIT);
      } else if (e.status === 400) {
        setError(
          'Your mastery of prerequisite units is too low to submit this quiz. ' +
          'Please go back and complete the earlier units first, or try the quiz again after reviewing the notes.'
        );
        setPhase(PHASE.SHOW_UNIT);
      } else {
        setError('Submission failed: ' + e.message);
        setPhase(PHASE.QUIZ);
      }
    }
  }

  async function handleAfterResult() {
    if (!quizResult?.bkt?.unit_passed) {
      // Failed — if quiz is now locked show the countdown, else allow retry
      if (secondsRemaining() > 0) {
        setPhase(PHASE.SHOW_UNIT);
      } else {
        await handleStartQuiz();
      }
      return;
    }
    // Passed — clear cache + lock, force fresh MCTS recommendation
    setQuizLock(null);
    sessionStorage.removeItem(REC_KEY);
    try {
      const gate = await flashApi.checkGate(userId);
      if (gate.can_proceed) {
        loadRecommendation(true);
      } else {
        setFlashGate({ due_cards: gate.due_cards, cards_due_count: gate.cards_due_count });
        setPhase(PHASE.FLASHCARDS);
      }
    } catch {
      loadRecommendation(true);
    }
  }

  function buildNoteContext(note) {
    const parts = [];
    // Rich format (notes.json)
    if (note.topic)                      parts.push('Topic: ' + note.topic);
    if (note.definition)                 parts.push('Definition:\n' + note.definition);
    if (note.key_concepts?.length)       parts.push('Key Concepts:\n' + note.key_concepts.join('\n- '));
    if (note.important_points?.length)   parts.push('Important Points:\n' + note.important_points.join('\n- '));
    if (note.code_examples?.length) {
      const codeStr = note.code_examples
        .map(e => (e.description ? e.description + ':\n' : '') + e.code)
        .join('\n\n');
      parts.push('Code Examples:\n' + codeStr);
    }
    if (note.explanation)                parts.push('Explanation:\n' + note.explanation);
    // Legacy flat format
    if (note.concept)                    parts.push(note.concept);
    if (note.code)                       parts.push('Code example:\n' + note.code);
    return parts.join('\n\n');
  }

  // ── PHASE RENDERS ─────────────────────────────────────────

  if (phase === PHASE.LOADING_REC) {
    return (
      <div className="page learn-page">
        <Spinner message="AI is finding your next unit… (MCTS running)" />
      </div>
    );
  }

  if (phase === PHASE.COMPLETE) {
    return (
      <div className="page learn-page page-centered">
        <div className="complete-card">
          <div className="complete-trophy">🏆</div>
          <h1>Curriculum Complete!</h1>
          <p>You've mastered all 14 units. Amazing work!</p>
          <Button onClick={() => navigate('/dashboard')}>View Dashboard</Button>
        </div>
      </div>
    );
  }

  if (phase === PHASE.FLASHCARDS) {
    return (
      <div className="page learn-page page-centered">
        <Card className="flash-gate-card">
          <div className="flash-gate-icon">⬜</div>
          <h2>Flashcard Review Due</h2>
          <p>Complete {flashGate?.cards_due_count} review{flashGate?.cards_due_count > 1 ? 's' : ''} before starting your next unit.</p>
          <div className="flash-due-list">
            {flashGate?.due_cards?.map(c => (
              <div key={c.unit_id} className="flash-due-item">
                <span>{domainIcon(c.domain)} {c.display_name}</span>
                <Badge color="#f59e0b">Due</Badge>
              </div>
            ))}
          </div>
          <Button onClick={() => navigate('/flashcards')} size="lg">Go to Flashcards →</Button>
        </Card>
      </div>
    );
  }

  // ── Unit overview ──────────────────────────────────────────
  if (phase === PHASE.SHOW_UNIT && rec) {
    return (
      <div className="page learn-page">
        {error && <Alert type="error">{error}</Alert>}

        <div className="unit-hero" style={{ '--domain-color': domainColor(rec.domain) }}>
          <div className="unit-hero-icon">{domainIcon(rec.domain)}</div>
          <div className="unit-hero-meta">
            <Badge color={domainColor(rec.domain)}>{rec.domain}</Badge>
            <h1 className="unit-hero-title">{rec.display_name}</h1>
            <p className="unit-hero-desc">{rec.description}</p>
          </div>
        </div>

        {rec.mcts_details?.candidates?.length > 0 && (
          <Card className="mcts-card">
            <div className="card-title">Why this unit? (AI reasoning)</div>
            <div className="mcts-candidates">
              {rec.mcts_details.candidates.map((c, i) => (
                <div key={c.unit_id} className={`mcts-row ${i === 0 ? 'mcts-top' : ''}`}>
                  <span className="mcts-rank">#{i + 1}</span>
                  <span className="mcts-name">{c.display_name}</span>
                  <div className="mcts-bar-wrap">
                    <div className="mcts-bar" style={{ width: `${c.avg_reward * 100}%` }} />
                  </div>
                  <span className="mcts-score">{(c.avg_reward * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          </Card>
        )}

        {rec.quiz_question && (
          <Card className="preview-card">
            <div className="card-title">Sample Question</div>
            <p className="preview-q">{rec.quiz_question.text}</p>
            <div className="preview-opts">
              {rec.quiz_question.options?.map((opt, i) => (
                <span key={i} className="preview-opt">{String.fromCharCode(65 + i)}. {opt}</span>
              ))}
            </div>
          </Card>
        )}

        {quizLock && secondsRemaining() > 0 ? (
          <div className="quiz-lock-banner">
            <div className="lock-icon">🔒</div>
            <div className="lock-text">
              <strong>Quiz locked — come back in</strong>
              <div className="lock-countdown">{formatCountdown(secondsRemaining())}</div>
              <span className="lock-sub">A fresh set of questions will be generated after the cooldown.</span>
            </div>
          </div>
        ) : (
          <div className="unit-actions">
            <Button size="lg" onClick={handleViewNotes} loading={notesLoading}>
              📖 Read Notes
            </Button>
            <Button variant="secondary" size="lg" onClick={handleStartQuiz}>
              ▶ Start Quiz
            </Button>
            <Button variant="ghost" onClick={() => { sessionStorage.removeItem(REC_KEY); loadRecommendation(true); }}>
              ↺ Get Different Unit
            </Button>
          </div>
        )}
      </div>
    );
  }

  // ── NOTES PHASE ────────────────────────────────────────────
  if (phase === PHASE.NOTES) {
    const chatCtx = rec ? {
      unit_id:      rec.unit_id,
      display_name: rec.display_name,
      domain:       rec.domain,
      unit_notes:   simplifyNote ? buildNoteContext(simplifyNote) : null,
    } : null;

    return (
      <div className="page learn-page">
        {/* Header */}
        <div className="notes-header">
          <div>
            <Badge color={domainColor(rec?.domain)}>
              {domainIcon(rec?.domain)} {rec?.domain}
            </Badge>
            <h1 className="page-title" style={{ marginTop: '0.5rem' }}>
              {rec?.display_name}
            </h1>
            <p className="page-subtitle">
              Read the notes below, then take the quiz when you're ready.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'flex-start' }}>
            <Button size="lg" onClick={handleStartQuiz}>▶ Start Quiz →</Button>
            <Button variant="ghost" onClick={() => setChatOpen(o => !o)}>
              {chatOpen ? 'Close Tutor' : '🤖 Ask AI Tutor'}
            </Button>
          </div>
        </div>

        {/* Notes + optional chat sidebar */}
        <div className="notes-layout">
          <div className="notes-main">
            {unitNotes.length === 0 ? (
              <Card>
                <p className="muted">No notes found for this unit in the dataset.</p>
                <Button onClick={handleStartQuiz} style={{ marginTop: '1rem' }}>Go to Quiz →</Button>
              </Card>
            ) : (
              unitNotes.map(({ topic, items }) => (
                <Card key={topic} className="notes-topic-card">
                  <div className="notes-topic-header">
                    <h3 className="notes-topic-title">{topic}</h3>
                    <Badge>{items.length} note{items.length > 1 ? 's' : ''}</Badge>
                  </div>

                  {items.map((note, ni) => {
                    const isRich = !!(note.definition || note.key_concepts);

                    if (isRich) {
                      // ── Rich format (notes.json) ────────────────────────
                      return (
                        <div key={ni} className="note-item">
                          {note.definition && (
                            <p className="note-definition">{note.definition}</p>
                          )}

                          {note.key_concepts?.length > 0 && (
                            <div className="note-section">
                              <div className="note-section-label">Key Concepts</div>
                              <ul className="note-bullets">
                                {note.key_concepts.map((kc, i) => (
                                  <li key={i}>{kc}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {note.rules_for_naming?.length > 0 && (
                            <div className="note-section">
                              <div className="note-section-label">Naming Rules</div>
                              <ul className="note-bullets">
                                {note.rules_for_naming.map((r, i) => (
                                  <li key={i}>{r}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {note.code_examples?.length > 0 && note.code_examples.map((ex, i) => (
                            <div key={i} className="note-code-block">
                              {ex.description && (
                                <div className="code-label">{ex.description}</div>
                              )}
                              <pre className="code-pre"><code>{ex.code}</code></pre>
                            </div>
                          ))}

                          {note.important_points?.length > 0 && (
                            <div className="note-section">
                              <div className="note-section-label">Important Points</div>
                              <ul className="note-bullets note-bullets-important">
                                {note.important_points.map((pt, i) => (
                                  <li key={i}>{pt}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {note.exam_questions?.length > 0 && (
                            <div className="note-section note-section-exam">
                              <div className="note-section-label">Practice Questions</div>
                              <ol className="note-bullets note-bullets-exam">
                                {note.exam_questions.map((q, i) => (
                                  <li key={i}>{q}</li>
                                ))}
                              </ol>
                            </div>
                          )}

                          {note.explanation && (
                            <p className="note-explanation">{note.explanation}</p>
                          )}

                          <button
                            className="note-simplify-btn"
                            onClick={() => { setSimplifyNote(note); setChatOpen(true); }}
                          >
                            💡 Ask AI to explain this
                          </button>
                        </div>
                      );
                    }

                    // ── Legacy flat format ──────────────────────────────
                    const skipCode = !note.code
                      || note.code.includes(`print('${topic}')`)
                      || note.code.includes("print('Hello')")
                      || note.code.trim() === '';
                    const skipIO  = !note.input_output
                      || note.input_output.includes('Example input')
                      || note.input_output.trim() === '';
                    const skipExp = !note.explanation
                      || note.explanation.includes('demonstrates how')
                      || note.explanation.includes('This example');

                    return (
                      <div key={note.id ?? ni} className="note-item">
                        {note.concept && (
                          <p className="note-concept">{note.concept}</p>
                        )}
                        {!skipCode && (
                          <div className="note-code-block">
                            <div className="code-label">Code Example</div>
                            <pre className="code-pre"><code>{note.code}</code></pre>
                          </div>
                        )}
                        {!skipIO && (
                          <div className="note-io">
                            <div className="code-label">Output</div>
                            <pre className="code-pre io-pre"><code>{note.input_output}</code></pre>
                          </div>
                        )}
                        {!skipExp && (
                          <p className="note-explanation">{note.explanation}</p>
                        )}
                        <button
                          className="note-simplify-btn"
                          onClick={() => { setSimplifyNote(note); setChatOpen(true); }}
                        >
                          💡 Ask AI to explain this
                        </button>
                      </div>
                    );
                  })}
                </Card>
              ))
            )}

            <div className="notes-bottom-cta">
              <Button size="lg" onClick={handleStartQuiz}>▶ I'm ready — Start Quiz</Button>
              <Button variant="ghost" onClick={() => setPhase(PHASE.SHOW_UNIT)}>← Back</Button>
            </div>
          </div>

          {chatOpen && (
            <div className="notes-chat-side">
              <ChatSidebar unitContext={chatCtx} currentQuestion={null} />
            </div>
          )}
        </div>
      </div>
    );
  }

  if (phase === PHASE.LOADING_QS) {
    return <div className="page learn-page"><Spinner message="Loading quiz questions…" /></div>;
  }

  if (phase === PHASE.SUBMITTING) {
    return <div className="page learn-page"><Spinner message="Scoring your quiz (IRT)…" /></div>;
  }

  if (phase === PHASE.QUIZ && questions.length > 0) {
    const q = questions[current];
    const answeredCount = Object.keys(answers).length;

    return (
      <div className="page learn-page">
        {error && <Alert type="error" onClose={() => setError('')}>{error}</Alert>}
        <div className="quiz-topbar">
          <div className="quiz-unit-name">{rec?.display_name}</div>
          <ProgressBar value={answeredCount} max={questions.length} color="var(--accent)" showPercent={false} />
          <div className="quiz-count">{current + 1}/{questions.length}</div>
        </div>

        <div className="quiz-layout">
          <div className="quiz-main">
            <div className="question-card">
              <div className="question-tags">
                <Badge color={difficultyColor(q.difficulty)}>{q.difficulty}</Badge>
                {q.tags?.map(t => <Badge key={t}>{t}</Badge>)}
              </div>
              <p className="question-text">{q.text}</p>

              <div className="options-list">
                {q.options.map((opt, idx) => {
                  let optClass = 'option-btn';
                  if (answers[q.question_id] === idx) optClass += ' option-selected';
                  if (instantFB) {
                    if (idx === instantFB.correct_idx) optClass += ' option-correct';
                    else if (answers[q.question_id] === idx) optClass += ' option-wrong';
                  }
                  return (
                    <button
                      key={idx}
                      className={optClass}
                      onClick={() => !instantFB && handleAnswer(q.question_id, idx)}
                      disabled={!!instantFB}
                    >
                      <span className="option-letter">{String.fromCharCode(65 + idx)}</span>
                      <span className="option-text">{opt}</span>
                      {instantFB && idx === instantFB.correct_idx && <span className="option-mark">✓</span>}
                      {instantFB && answers[q.question_id] === idx && idx !== instantFB.correct_idx && <span className="option-mark">✕</span>}
                    </button>
                  );
                })}
              </div>

              {instantFB && (
                <div className={`feedback-box ${instantFB.is_correct ? 'feedback-correct' : 'feedback-wrong'}`}>
                  <strong>{instantFB.is_correct ? '✓ Correct!' : '✕ Incorrect'}</strong>
                  {instantFB.explanation && <p>{instantFB.explanation}</p>}
                </div>
              )}
            </div>

            <div className="quiz-nav">
              <Button variant="ghost" onClick={() => { setInstantFB(null); setCurrent(c => c - 1); }} disabled={current === 0}>
                ← Prev
              </Button>
              <div className="quiz-nav-center">
                {!instantFB && answers[q.question_id] != null && (
                  <Button variant="secondary" size="sm" onClick={handleCheckAnswer}>Check Answer</Button>
                )}
                {instantFB && current < questions.length - 1 && (
                  <Button onClick={handleNext}>Next →</Button>
                )}
              </div>
              {current === questions.length - 1 ? (
                <Button onClick={handleSubmitQuiz} disabled={answeredCount < questions.length}>Submit All ✓</Button>
              ) : (
                <Button onClick={handleNext} disabled={current >= questions.length - 1}>Next →</Button>
              )}
            </div>

            <div className="dot-nav">
              {questions.map((qq, i) => (
                <button
                  key={i}
                  className={`dot ${i === current ? 'dot-current' : ''} ${answers[qq.question_id] != null ? 'dot-answered' : ''}`}
                  onClick={() => { setInstantFB(null); setCurrent(i); }}
                />
              ))}
            </div>
          </div>

          <div className={`chat-side ${chatOpen ? 'chat-open' : ''}`}>
            <button className="chat-toggle" onClick={() => setChatOpen(o => !o)}>
              {chatOpen ? '→ Close Tutor' : '← AI Tutor'}
            </button>
            {chatOpen && rec && (
              <ChatSidebar unitContext={rec} currentQuestion={q} />
            )}
          </div>
        </div>
      </div>
    );
  }

  if (phase === PHASE.RESULT && quizResult) {
    const passed = quizResult.bkt?.unit_passed;
    return (
      <div className="page learn-page page-centered">
        <div className={`result-card ${passed ? 'result-pass' : 'result-fail'}`}>
          <div className="result-emoji">{passed ? '🎉' : '📖'}</div>
          <h2 className="result-heading">{passed ? 'Unit Passed!' : 'Not Quite Yet'}</h2>
          {quizResult.irt?.mastery_level && (
            <div className="result-mastery-badge">
              <Badge color={
                quizResult.irt.mastery_level === 'Mastered'   ? '#10b981' :
                quizResult.irt.mastery_level === 'Proficient' ? '#6366f1' :
                quizResult.irt.mastery_level === 'Developing' ? '#f59e0b' : '#94a3b8'
              }>
                {quizResult.irt.mastery_level.toUpperCase()}
              </Badge>
            </div>
          )}
          <p className="result-explanation">{quizResult.irt?.explanation}</p>

          <div className="result-stats">
            <div className="stat-box">
              <div className="stat-num">{quizResult.raw?.correct}/{quizResult.raw?.total}</div>
              <div className="stat-lbl">Correct</div>
            </div>
            <div className="stat-box">
              <div className="stat-num">{quizResult.raw?.percent?.toFixed(0)}%</div>
              <div className="stat-lbl">Score</div>
            </div>
            <div className="stat-box">
              <div className="stat-num">{quizResult.irt?.mastery_pct ?? (quizResult.irt?.mastery * 100)?.toFixed(0)}%</div>
              <div className="stat-lbl">Mastery (IRT)</div>
            </div>
            {passed && (
              <div className="stat-box">
                <div className="stat-num">🔥{quizResult.progress?.streak_days}</div>
                <div className="stat-lbl">Day Streak</div>
              </div>
            )}
          </div>

          {quizResult.bkt?.skill_updates?.length > 0 && (
            <div className="skill-updates">
              {quizResult.bkt.skill_updates.map(su => (
                <div key={su.skill} className="skill-update-row">
                  <span className="su-skill">{su.skill}</span>
                  <span className="su-before">{(su.p_L_before * 100).toFixed(0)}%</span>
                  <span className="su-arrow">→</span>
                  <span className="su-after" title="BKT blended mastery">
                    {su.bkt_mastery_pct ?? (su.p_L_after * 100).toFixed(0)}%
                  </span>
                  <Badge color={
                    (su.irt_mastery_level || su.mastery_level) === 'Mastered'  ? '#10b981' :
                    (su.irt_mastery_level || su.mastery_level) === 'Proficient' ? '#6366f1' :
                    (su.irt_mastery_level || su.mastery_level) === 'Developing' ? '#f59e0b' : '#94a3b8'
                  }>
                    {su.irt_mastery_level || su.mastery_level}
                  </Badge>
                </div>
              ))}
            </div>
          )}

          {quizResult.stuck_alert && (
            <Alert type="warning" title="You seem stuck!">
              Failed {quizResult.consecutive_failures} times. Consider reviewing prerequisites:
              <ul>
                {quizResult.prereq_review_suggestions?.map(s => (
                  <li key={s.prereq_skill}>{s.message}</li>
                ))}
              </ul>
            </Alert>
          )}

          <details className="result-detail">
            <summary>Question Breakdown</summary>
            <div className="breakdown-grid">
              {quizResult.question_detail?.map(qd => (
                <div key={qd.question_id} className={`breakdown-item ${qd.is_correct ? 'correct' : 'wrong'}`}>
                  <span>{qd.is_correct ? '✓' : '✕'}</span>
                  <span>{qd.question_id}</span>
                  <Badge color={difficultyColor(qd.difficulty)}>{qd.difficulty}</Badge>
                </div>
              ))}
            </div>
          </details>

          <div className="result-actions">
            <Button size="lg" onClick={handleAfterResult}>
              {passed ? '→ Continue' : '↺ Retry Quiz'}
            </Button>
            {!passed && unitNotes.length > 0 && (
              <Button variant="secondary" onClick={() => setPhase(PHASE.NOTES)}>
                📖 Review Notes
              </Button>
            )}
            <Button variant="ghost" onClick={() => navigate('/mistakes')}>
              View Weak Areas
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return <Spinner message="Loading…" />;
}
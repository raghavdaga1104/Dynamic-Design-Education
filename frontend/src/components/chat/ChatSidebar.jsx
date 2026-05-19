// src/components/chat/ChatSidebar.jsx
// Fix 1: Reads currentUnit from AppContext if no prop supplied
// Fix 2: unit_notes always sent so RAG uses direct context
// Fix 3: initialMode prop — 'simplify' auto-triggers when note simplify btn clicked
// Fix 4: Chat history cleared when unit changes
// Fix 5: Friendly error messages per status code

import { useState, useRef, useEffect } from 'react';
import { useApp } from '../../context/AppContext';
import { chat as chatApi } from '../../services/api';
import { Button, Spinner } from '../ui';

const MODES = [
  { id: 'question', label: '❓ Ask',      desc: 'Ask anything about this unit' },
  { id: 'hint',     label: '💡 Hint',     desc: 'Get a Socratic hint for this question' },
  { id: 'simplify', label: '📖 Simplify', desc: 'Simplify or explain a note' },
];

export default function ChatSidebar({ unitContext: propContext, currentQuestion, initialMode }) {
  const { userId, currentUnit } = useApp();
  // Use prop if provided, fall back to global AppContext.currentUnit
  const unitContext = propContext || currentUnit;

  const [mode,    setMode]    = useState(initialMode || 'question');
  const [input,   setInput]   = useState('');
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  // Clear history when switching to a different unit
  useEffect(() => {
    setHistory([]);
    setInput('');
  }, [unitContext?.unit_id]);

  // Auto-trigger simplify when initialMode changes to 'simplify'
  useEffect(() => {
    if (initialMode === 'simplify') {
      setMode('simplify');
      // Auto-send if we have note content
      if (unitContext?.unit_notes) {
        handleSend('simplify');
      }
    }
  }, [initialMode, unitContext?.unit_notes]); // eslint-disable-line

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [history]);

  async function handleSend(overrideMode) {
    const activeMode = overrideMode || mode;
    let question = '';

    if (activeMode === 'question') {
      question = input.trim();
      if (!question) return;
    } else if (activeMode === 'hint') {
      question = currentQuestion?.text || input.trim();
      if (!question) {
        setHistory(h => [...h, {
          role: 'system',
          content: 'Navigate to a quiz question first, then click Hint — or type the question text here.',
        }]);
        return;
      }
    }
    // simplify: question is empty, backend uses unit_notes

    const userLabel =
      activeMode === 'simplify' ? 'Please explain / simplify this note.' :
      activeMode === 'hint'     ? `Give me a hint for: "${question.slice(0, 80)}${question.length > 80 ? '…' : ''}"` :
      question;

    setHistory(h => [...h, { role: 'user', content: userLabel }]);
    setInput('');
    setLoading(true);

    try {
      const res = await chatApi.ask(userId, question, unitContext, activeMode);
      setHistory(h => [...h, {
        role: 'ai',
        content: res.answer,
        contextUsed: res.context_used,
      }]);
    } catch (e) {
      const msg =
        e.status === 408 ? 'Timed out — the LLM may be slow. Try again in a moment.' :
        e.status === 503 ? 'Server unavailable. Try again shortly.' :
        e.isCircuit      ? 'Too many errors. Waiting 30s before retrying.' :
        `Could not get a response. ${e.message}`;
      setHistory(h => [...h, { role: 'ai', content: msg, error: true }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chat-sidebar">
      {/* Mode tabs */}
      <div className="chat-modes">
        {MODES.map(m => (
          <button
            key={m.id}
            className={`chat-mode-btn ${mode === m.id ? 'mode-active' : ''}`}
            onClick={() => { setMode(m.id); setInput(''); }}
            title={m.desc}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* Unit context indicator */}
      {unitContext?.display_name && (
        <div className="chat-unit-label">📖 {unitContext.display_name}</div>
      )}

      {/* Messages */}
      <div className="chat-messages">
        {history.length === 0 && (
          <div className="chat-empty">
            <p>👋 Hi! I'm your AI tutor.</p>
            {unitContext?.display_name
              ? <p>Ask me anything about <strong>{unitContext.display_name}</strong>.</p>
              : <p>Open a unit to get started.</p>
            }
            <p className="chat-modes-hint">
              Try <strong>Hint</strong> during a quiz question, or click<br/>
              <em>"Ask AI to explain this"</em> on any note.
            </p>
          </div>
        )}

        {history.map((msg, i) => (
          <div
            key={i}
            className={[
              'chat-msg',
              msg.role === 'user'   ? 'msg-user'   : '',
              msg.role === 'ai'     ? 'msg-ai'      : '',
              msg.role === 'system' ? 'msg-system'  : '',
              msg.error             ? 'msg-error'   : '',
            ].filter(Boolean).join(' ')}
          >
            {msg.role !== 'system' && (
              <div className="msg-role">
                {msg.role === 'user' ? 'You' : '🤖 DDE Tutor'}
                {msg.contextUsed === false && msg.role === 'ai' && (
                  <span className="no-context-badge"> · answered from knowledge</span>
                )}
              </div>
            )}
            <div className="msg-content" style={{ whiteSpace: 'pre-wrap' }}>
              {msg.content}
            </div>
          </div>
        ))}

        {loading && (
          <div className="chat-msg msg-ai">
            <div className="msg-role">🤖 DDE Tutor</div>
            <div className="msg-content"><Spinner size="sm" /></div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Input row */}
      <div className="chat-input-row">
        {mode !== 'simplify' && (
          <input
            className="chat-input"
            placeholder={
              mode === 'hint'
                ? currentQuestion?.text
                  ? 'Send for a hint on the current question…'
                  : 'Type or paste the question here…'
                : 'Ask anything about this topic…'
            }
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !loading) handleSend(); }}
            disabled={loading}
          />
        )}
        <Button
          onClick={() => handleSend()}
          loading={loading}
          disabled={loading || (mode === 'question' && !input.trim())}
          size="sm"
        >
          {mode === 'simplify' ? 'Explain' : 'Send'}
        </Button>
      </div>
    </div>
  );
}
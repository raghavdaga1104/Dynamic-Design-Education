// pages/Flashcards.jsx
// ─────────────────────────────────────────────────────────────
// SM-2 spaced repetition review screen.
// Shows: schedule, due cards, flip interaction, quality rating.
// After all reviews, redirects back to learn.
// ─────────────────────────────────────────────────────────────

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { flashcard as flashApi } from '../services/api';
import { Card, Spinner, Badge, Button, Alert, ProgressBar, EmptyState } from '../components/ui';
import { domainIcon, domainColor } from '../utils/helpers';

const QUALITY_LABELS = [
  { q: 0, label: 'Blackout',   color: '#ef4444', desc: 'No memory at all' },
  { q: 1, label: 'Wrong',      color: '#f97316', desc: 'Incorrect, but recalled after seeing' },
  { q: 2, label: 'Barely',     color: '#f59e0b', desc: 'Incorrect but felt familiar' },
  { q: 3, label: 'Hard',       color: '#84cc16', desc: 'Correct with great effort' },
  { q: 4, label: 'Good',       color: '#10b981', desc: 'Correct with small hesitation' },
  { q: 5, label: 'Perfect',    color: '#06b6d4', desc: 'Instant correct recall' },
];

export default function Flashcards() {
  const { userId } = useApp();
  const navigate = useNavigate();

  const [schedule, setSchedule] = useState(null);
  const [dueCards, setDueCards] = useState([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [flipped, setFlipped]   = useState(false);
  const [reviewing, setReviewing] = useState(false); // true when in active review
  const [loading, setLoading]   = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]       = useState('');
  const [done, setDone]         = useState(false);

  useEffect(() => {
    loadSchedule();
  }, [userId]);

  async function loadSchedule() {
    setLoading(true);
    try {
      const [sched, due] = await Promise.all([
        flashApi.getSchedule(userId),
        flashApi.getDue(userId),
      ]);
      setSchedule(sched);
      // Build due card objects from schedule
      const dueIds = new Set(due.due_units);
      const cards = sched.schedule.filter(c => dueIds.has(c.unit_id));
      setDueCards(cards);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleQualityRate(quality) {
    if (currentIdx >= dueCards.length) return;
    const card = dueCards[currentIdx];
    setSubmitting(true);
    try {
      const result = await flashApi.review(userId, card.unit_id, quality, schedule?.current_day || 0);
      if (result.can_proceed && result.cards_remaining === 0) {
        setDone(true);
      } else {
        setFlipped(false);
        setCurrentIdx(i => i + 1);
        if (currentIdx + 1 >= dueCards.length) setDone(true);
      }
    } catch (e) {
      setError('Failed to submit review: ' + e.message);
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <div className="page"><Spinner message="Loading flashcard schedule…" /></div>;
  if (error)   return <div className="page"><Alert type="error">{error}</Alert></div>;

  // ── Completion screen ─────────────────────────────────────
  if (done) {
    return (
      <div className="page flash-page page-centered">
        <Card className="flash-done-card">
          <div className="flash-done-icon">✓</div>
          <h2>All Reviews Done!</h2>
          <p>Great job. Your memory intervals have been updated.</p>
          <Button size="lg" onClick={() => navigate('/learn')}>
            Continue Learning →
          </Button>
          <Button variant="ghost" onClick={loadSchedule}>
            View Schedule
          </Button>
        </Card>
      </div>
    );
  }

  // ── Active review ─────────────────────────────────────────
  if (reviewing && dueCards.length > 0) {
    const card = dueCards[currentIdx];
    if (!card) {
      setDone(true);
      return null;
    }

    return (
      <div className="page flash-page page-centered">
        <div className="flash-review-header">
          <ProgressBar
            value={currentIdx}
            max={dueCards.length}
            color="var(--accent)"
            label={`${currentIdx} of ${dueCards.length} reviewed`}
          />
        </div>

        {/* Flashcard */}
        <div className={`flashcard ${flipped ? 'flipped' : ''}`} onClick={() => setFlipped(f => !f)}>
          <div className="flashcard-inner">
            <div className="flashcard-front">
              <div className="fc-domain">{domainIcon(card.domain)} {card.domain}</div>
              <h2 className="fc-title">{card.display_name}</h2>
              <p className="fc-hint">Click to reveal</p>
            </div>
            <div className="flashcard-back">
              <div className="fc-domain">Skills Taught</div>
              <div className="fc-skills">
                {/* Display what's known about the card */}
                <p>Unit: <strong>{card.display_name}</strong></p>
                <p>Interval: {card.interval} day{card.interval !== 1 ? 's' : ''}</p>
                <p>Reviews: {card.repetitions}</p>
                <p>Ease: {card.ease_factor?.toFixed(2)}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Quality rating — only after flip */}
        {flipped && (
          <div className="quality-rating">
            <p className="quality-prompt">How well did you remember?</p>
            <div className="quality-buttons">
              {QUALITY_LABELS.map(({ q, label, color, desc }) => (
                <button
                  key={q}
                  className="quality-btn"
                  style={{ '--q-color': color }}
                  onClick={() => handleQualityRate(q)}
                  disabled={submitting}
                  title={desc}
                >
                  <span className="q-num">{q}</span>
                  <span className="q-label">{label}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {!flipped && (
          <p className="flip-hint">↑ Click the card to flip it, then rate your recall</p>
        )}

        {error && <Alert type="error">{error}</Alert>}
      </div>
    );
  }

  // ── Schedule overview ─────────────────────────────────────
  return (
    <div className="page flash-page">
      <div className="page-header">
        <h1 className="page-title">Flashcards</h1>
        <div className="flash-summary">
          <Badge color="#f59e0b">⬜ {schedule?.due_today || 0} Due Today</Badge>
          <Badge color="#64748b">📅 {schedule?.total_cards || 0} Total</Badge>
        </div>
      </div>

      {dueCards.length > 0 ? (
        <Card className="flash-due-card">
          <div className="card-title">Due for Review</div>
          <div className="flash-due-list">
            {dueCards.map(c => (
              <div key={c.unit_id} className="flash-due-item">
                <span className="flash-domain">{domainIcon(c.domain)}</span>
                <span className="flash-name">{c.display_name}</span>
                <Badge color="#f59e0b">Due</Badge>
              </div>
            ))}
          </div>
          <Button
            size="lg"
            className="btn-full"
            onClick={() => { setCurrentIdx(0); setFlipped(false); setReviewing(true); }}
          >
            Start Review ({dueCards.length} cards)
          </Button>
        </Card>
      ) : (
        <EmptyState
          icon="✓"
          title="No reviews due"
          description="Check back tomorrow. Your next scheduled review is upcoming."
        />
      )}

      {/* Full schedule */}
      {schedule?.schedule?.length > 0 && (
        <Card className="flash-schedule-card">
          <div className="card-title">Full Schedule</div>
          <table className="schedule-table">
            <thead>
              <tr>
                <th>Unit</th>
                <th>Due Day</th>
                <th>Interval</th>
                <th>Ease</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {schedule.schedule.map(c => (
                <tr key={c.unit_id} className={c.is_due_today ? 'row-due' : ''}>
                  <td>{c.display_name}</td>
                  <td>Day {c.due_day}</td>
                  <td>{c.interval}d</td>
                  <td>{c.ease_factor?.toFixed(2)}</td>
                  <td>
                    {c.is_due_today
                      ? <Badge color="#f59e0b">Due Today</Badge>
                      : <Badge color="#64748b">In {c.days_until}d</Badge>
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

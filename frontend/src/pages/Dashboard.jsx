// pages/Dashboard.jsx
// ─────────────────────────────────────────────────────────────
// Main home screen after onboarding.
// Shows: progress overview, streak, mastery summary, 
// next recommended unit, and flashcard due alert.
// ─────────────────────────────────────────────────────────────

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { learner as learnerApi, flashcard as flashApi } from '../services/api';
import { Card, Spinner, Badge, ProgressBar, Alert, Button } from '../components/ui';
import { masteryLabel, masteryColor, masteryPercent, domainIcon, domainColor } from '../utils/helpers';

export default function Dashboard() {
  const { userId } = useApp();
  const navigate = useNavigate();

  const [state, setState]   = useState(null);
  const [gate, setGate]     = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState('');

  useEffect(() => {
    if (!userId) { navigate('/'); return; }
    loadData();
  }, [userId]);

  async function loadData() {
    setLoading(true);
    setError('');
    try {
      const [learnerState, flashGate] = await Promise.all([
        learnerApi.getState(userId),
        flashApi.checkGate(userId),
      ]);
      setState(learnerState);
      setGate(flashGate);
    } catch (e) {
      setError('Could not load your progress. ' + e.message);
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <Spinner message="Loading your dashboard…" />;
  if (error)   return <Alert type="error">{error}</Alert>;
  if (!state)  return null;

  const { progress } = state;
  const mastery = progress?.mastery_summary || [];

  return (
    <div className="page dash-page">
      {/* ── Flash card alert banner ── */}
      {gate?.reviews_due && (
        <Alert type="warning" title="Flashcard reviews due!">
          You have {gate.cards_due_count} card{gate.cards_due_count > 1 ? 's' : ''} due for review
          before you can proceed to your next unit.{' '}
          <button className="inline-link" onClick={() => navigate('/flashcards')}>
            Review now →
          </button>
        </Alert>
      )}

      {/* ── Top stats row ── */}
      <div className="dash-stats-row">
        <Card className="stat-card">
          <div className="stat-icon">🔥</div>
          <div className="stat-val">{progress?.streak_days ?? 0}</div>
          <div className="stat-lbl">Day Streak</div>
        </Card>

        <Card className="stat-card">
          <div className="stat-icon">📚</div>
          <div className="stat-val">{progress?.units_completed ?? 0}/{progress?.units_total ?? 14}</div>
          <div className="stat-lbl">Units Done</div>
        </Card>

        <Card className="stat-card">
          <div className="stat-icon">⬜</div>
          <div className="stat-val">{gate?.cards_due_count ?? 0}</div>
          <div className="stat-lbl">Cards Due</div>
        </Card>

        <Card className="stat-card">
          <div className="stat-icon">⟡</div>
          <div className="stat-val">{progress?.percent_complete?.toFixed(0) ?? 0}%</div>
          <div className="stat-lbl">Complete</div>
        </Card>
      </div>

      {/* ── Overall progress bar ── */}
      <Card className="dash-progress-card">
        <div className="card-title">Overall Progress</div>
        <ProgressBar
          value={progress?.percent_complete ?? 0}
          max={100}
          color="var(--accent)"
          label={`${progress?.units_completed} of ${progress?.units_total} units completed`}
        />
      </Card>

      {/* ── Mastery skills grid ── */}
      <Card className="dash-skills-card">
        <div className="card-title">Skill Mastery</div>
        <div className="skills-grid">
          {mastery.length === 0 ? (
            <p className="muted">No skills tracked yet. Complete a quiz to see mastery.</p>
          ) : (
            mastery.map(skill => (
              <div key={skill.skill} className="skill-row">
                <div className="skill-info">
                  <span className="skill-name">{skill.skill}</span>
                  <span className={`skill-level ${masteryColor(skill.mastery)}`}>
                    {masteryLabel(skill.mastery)}
                  </span>
                </div>
                <div className="skill-bar-wrap">
                  <div
                    className="skill-bar-fill"
                    style={{
                      width: masteryPercent(skill.mastery),
                      backgroundColor: skill.mastery >= 0.8 ? '#10b981'
                        : skill.mastery >= 0.6 ? '#6366f1'
                        : skill.mastery >= 0.3 ? '#f59e0b' : '#64748b',
                    }}
                  />
                </div>
                <span className="skill-pct">{masteryPercent(skill.mastery)}</span>
              </div>
            ))
          )}
        </div>
      </Card>

      {/* ── Quick actions ── */}
      <div className="dash-actions">
        <Button size="lg" onClick={() => navigate('/learn')}>
          ▶ Continue Learning
        </Button>
        {gate?.reviews_due && (
          <Button size="lg" variant="secondary" onClick={() => navigate('/flashcards')}>
            ⬜ Review Flashcards ({gate.cards_due_count})
          </Button>
        )}
        <Button variant="ghost" onClick={() => navigate('/skill-tree')}>
          ⟡ View Skill Tree
        </Button>
        <Button variant="ghost" onClick={() => navigate('/mistakes')}>
          ◈ Weak Areas
        </Button>
      </div>

      {/* ── Completed units ── */}
      {state.completed_units?.length > 0 && (
        <Card className="dash-completed-card">
          <div className="card-title">Completed Units</div>
          <div className="completed-list">
            {state.completed_units.map(uid => (
              <Badge key={uid} color="#10b981" className="completed-badge">
                ✓ {uid.replace('UNIT', 'U').replace(/_/g, ' ')}
              </Badge>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

// pages/Dashboard.jsx — redesigned
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { learner as learnerApi, flashcard as flashApi } from '../services/api';
import { Spinner, Alert } from '../components/ui';
import { masteryLabel, masteryColor, masteryPercent } from '../utils/helpers';

function StatCard({ icon, value, label, accent, onClick }) {
  return (
    <div className={`ds-stat-card ${onClick ? 'ds-stat-clickable' : ''}`} onClick={onClick}>
      <div className="ds-stat-icon-wrap" style={{ background: accent + '20', color: accent }}>
        {icon}
      </div>
      <div className="ds-stat-body">
        <span className="ds-stat-val">{value}</span>
        <span className="ds-stat-lbl">{label}</span>
      </div>
      <div className="ds-stat-glow" style={{ background: accent }} />
    </div>
  );
}

function SkillBar({ skill }) {
  const pct   = parseFloat(masteryPercent(skill.mastery));
  const color = skill.mastery >= 0.8 ? '#10b981'
              : skill.mastery >= 0.6 ? '#6c7eff'
              : skill.mastery >= 0.3 ? '#f59e0b' : '#475569';
  const label = masteryLabel(skill.mastery);

  return (
    <div className="ds-skill-row">
      <div className="ds-skill-meta">
        <span className="ds-skill-name">{skill.skill}</span>
        <span className="ds-skill-badge" style={{ color, borderColor: color + '40', background: color + '15' }}>
          {label}
        </span>
      </div>
      <div className="ds-skill-track">
        <div
          className="ds-skill-fill"
          style={{ width: `${pct}%`, background: `linear-gradient(90deg, ${color}aa, ${color})` }}
        />
      </div>
      <span className="ds-skill-pct" style={{ color }}>{pct}%</span>
    </div>
  );
}

export default function Dashboard() {
  const { userId, userName } = useApp();
  const navigate = useNavigate();

  const [state,   setState]   = useState(null);
  const [gate,    setGate]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState('');

  useEffect(() => {
    if (!userId) { navigate('/login'); return; }
    load();
  }, [userId]);

  async function load() {
    setLoading(true); setError('');
    try {
      const [s, g] = await Promise.all([
        learnerApi.getState(userId),
        flashApi.checkGate(userId),
      ]);
      setState(s); setGate(g);
    } catch (e) {
      setError('Could not load your progress. ' + e.message);
    } finally { setLoading(false); }
  }

  if (loading) return <Spinner message="Loading dashboard…" />;
  if (error)   return <div className="page"><Alert type="error">{error}</Alert></div>;
  if (!state)  return null;

  const { progress } = state;
  const mastery  = progress?.mastery_summary || [];
  const pct      = progress?.percent_complete ?? 0;
  const streak   = progress?.streak_days ?? 0;
  const done     = progress?.units_completed ?? 0;
  const total    = progress?.units_total ?? 14;
  const cardsDue = gate?.cards_due_count ?? 0;

  // greeting
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
  const firstName = userName?.split(' ')[0] || 'Learner';

  return (
    <div className="page ds-page">

      {/* ── Header ── */}
      <div className="ds-header">
        <div>
          <h1 className="ds-greeting">{greeting}, {firstName} 👋</h1>
          <p className="ds-sub">Here's where you stand today.</p>
        </div>
        <button className="ds-continue-btn" onClick={() => navigate('/learn')}>
          ▶ &nbsp;Continue Learning
        </button>
      </div>

      {/* ── Flashcard alert ── */}
      {gate?.reviews_due && (
        <div className="ds-alert" onClick={() => navigate('/flashcards')}>
          <span className="ds-alert-icon">⬜</span>
          <span className="ds-alert-text">
            <strong>{cardsDue} flashcard{cardsDue > 1 ? 's' : ''} due</strong>
            {' '}— review before your next unit
          </span>
          <span className="ds-alert-arrow">→</span>
        </div>
      )}

      {/* ── Stats ── */}
      <div className="ds-stats">
        <StatCard icon="🔥" value={streak}            label="Day Streak"   accent="#f97316" />
        <StatCard icon="📚" value={`${done}/${total}`} label="Units Done"   accent="#6c7eff" />
        <StatCard icon="⬜" value={cardsDue}           label="Cards Due"    accent="#a78bfa"
          onClick={cardsDue > 0 ? () => navigate('/flashcards') : null} />
        <StatCard icon="⟡" value={`${pct.toFixed(0)}%`} label="Complete"  accent="#10b981" />
      </div>

      {/* ── Progress ── */}
      <div className="ds-section">
        <div className="ds-section-head">
          <span className="ds-section-title">Overall Progress</span>
          <span className="ds-section-badge">{done} of {total} units</span>
        </div>
        <div className="ds-progress-track">
          <div className="ds-progress-fill" style={{ width: `${pct}%` }} />
          <span className="ds-progress-label">{pct.toFixed(0)}%</span>
        </div>
      </div>

      {/* ── Two columns: skills + actions ── */}
      <div className="ds-body">

        {/* Skills */}
        <div className="ds-card ds-skills-card">
          <div className="ds-card-head">
            <span className="ds-card-title">Skill Mastery</span>
            <button className="ds-card-link" onClick={() => navigate('/skill-tree')}>
              View tree →
            </button>
          </div>
          {mastery.length === 0 ? (
            <div className="ds-empty">
              <span className="ds-empty-icon">◈</span>
              <p>No skills tracked yet.</p>
              <button className="ds-empty-btn" onClick={() => navigate('/learn')}>Start learning</button>
            </div>
          ) : (
            <div className="ds-skills-list">
              {mastery.map(s => <SkillBar key={s.skill} skill={s} />)}
            </div>
          )}
        </div>

        {/* Right column */}
        <div className="ds-right-col">

          {/* Quick actions */}
          <div className="ds-card ds-actions-card">
            <div className="ds-card-head">
              <span className="ds-card-title">Quick Actions</span>
            </div>
            <div className="ds-quick-actions">
              {[
                { icon: '▶', label: 'Continue Learning', sub: 'Pick up where you left off', path: '/learn',      accent: '#6c7eff' },
                { icon: '⬜', label: 'Flashcards',        sub: `${cardsDue} cards due`,      path: '/flashcards', accent: '#a78bfa' },
                { icon: '⟡', label: 'Skill Tree',         sub: 'See your knowledge map',     path: '/skill-tree', accent: '#10b981' },
                { icon: '◈', label: 'Weak Areas',         sub: 'Focus on your gaps',          path: '/mistakes',   accent: '#f59e0b' },
              ].map(a => (
                <button key={a.path} className="ds-action-row" onClick={() => navigate(a.path)}>
                  <div className="ds-action-icon" style={{ background: a.accent + '20', color: a.accent }}>
                    {a.icon}
                  </div>
                  <div className="ds-action-text">
                    <span className="ds-action-label">{a.label}</span>
                    <span className="ds-action-sub">{a.sub}</span>
                  </div>
                  <span className="ds-action-chevron">›</span>
                </button>
              ))}
            </div>
          </div>

          {/* Completed units */}
          {state.completed_units?.length > 0 && (
            <div className="ds-card ds-completed-card">
              <div className="ds-card-head">
                <span className="ds-card-title">Completed</span>
                <span className="ds-section-badge">{state.completed_units.length}</span>
              </div>
              <div className="ds-completed-list">
                {state.completed_units.map(uid => (
                  <div key={uid} className="ds-completed-item">
                    <span className="ds-completed-check">✓</span>
                    <span className="ds-completed-name">{uid.replace('UNIT', 'U').replace(/_/g, ' ')}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
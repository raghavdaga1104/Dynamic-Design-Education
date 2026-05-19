// pages/Mistakes.jsx
// ─────────────────────────────────────────────────────────────
// Shows learner's weak areas, insights, mistake log,
// and concept health breakdown. Uses Tabs layout.
// ─────────────────────────────────────────────────────────────

import { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { mistakes as mistakesApi } from '../services/api';
import { Card, Spinner, Alert, Badge, Tabs, EmptyState, ProgressBar } from '../components/ui';
import { difficultyColor } from '../utils/helpers';

const TABS = [
  { id: 'insights', label: 'Insights', icon: '◈' },
  { id: 'concepts', label: 'Concepts', icon: '◉' },
  { id: 'log',      label: 'History',  icon: '📋' },
];

export default function Mistakes() {
  const { userId } = useApp();

  const [tab, setTab]           = useState('insights');
  const [insights, setInsights] = useState(null);
  const [concepts, setConcepts] = useState(null);
  const [log, setLog]           = useState(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState('');

  useEffect(() => {
    loadAll();
  }, [userId]);

  async function loadAll() {
    setLoading(true);
    setError('');
    try {
      const [ins, con, lg] = await Promise.all([
        mistakesApi.getInsights(userId),
        mistakesApi.getConceptSummary(userId),
        mistakesApi.getLog(userId),
      ]);
      setInsights(ins);
      setConcepts(con);
      setLog(lg);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <div className="page"><Spinner message="Analysing your weak areas…" /></div>;
  if (error)   return <div className="page"><Alert type="error">{error}</Alert></div>;

  return (
    <div className="page mistakes-page">
      <div className="page-header">
        <h1 className="page-title">Weak Areas</h1>
        {insights?.stats && (
          <div className="mistakes-stats-row">
            <span>📊 {insights.stats.week_mistakes} mistakes this week</span>
            <span>✓ {insights.stats.week_correct} correct this week</span>
            <span>🔍 {insights.stats.concepts_tracked} concepts tracked</span>
          </div>
        )}
      </div>

      <Tabs tabs={TABS} activeTab={tab} onTabChange={setTab} />

      {/* ── Insights Tab ── */}
      {tab === 'insights' && insights && (
        <div className="tab-content">
          {/* Summary */}
          {insights.summary && (
            <Card className="insight-summary-card">
              <p>{insights.summary}</p>
            </Card>
          )}

          {/* Weekly insights */}
          {insights.weekly_insights?.length > 0 && (
            <Card>
              <div className="card-title">This Week</div>
              <ul className="insight-list">
                {insights.weekly_insights.map((ins, i) => (
                  <li key={i} className="insight-item">
                    <span className="insight-bullet">◈</span> {ins}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Top weaknesses */}
          {insights.top_weaknesses?.length > 0 && (
            <Card>
              <div className="card-title">Top Weaknesses</div>
              <div className="weakness-list">
                {insights.top_weaknesses.map(w => (
                  <div key={w.concept} className="weakness-row">
                    <div className="weakness-top">
                      <span className="weakness-name">{w.concept}</span>
                      <Badge color="#ef4444">Score: {w.weakness_score?.toFixed(1)}</Badge>
                    </div>
                    <div className="weakness-bar-row">
                      <span className="weakness-stat">Wrong: {w.wrong_count}/{w.total_attempts}</span>
                      <ProgressBar
                        value={w.wrong_rate * 100}
                        max={100}
                        color="#ef4444"
                        showPercent={false}
                      />
                      <span className="weakness-rate">{(w.wrong_rate * 100).toFixed(0)}% wrong</span>
                    </div>
                    <div className="weakness-diff">
                      {Object.entries(w.difficulty_breakdown || {}).map(([d, cnt]) => (
                        cnt > 0 && (
                          <Badge key={d} color={difficultyColor(d)}>{d}: {cnt}</Badge>
                        )
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Improvement tips */}
          {insights.improvement_tips?.length > 0 && (
            <Card>
              <div className="card-title">Improvement Tips</div>
              <div className="tips-list">
                {insights.improvement_tips.map(tip => (
                  <div key={tip.concept} className="tip-card">
                    <div className="tip-header">
                      <span className="tip-concept">{tip.concept}</span>
                      <Badge color={tip.priority === 'high' ? '#ef4444' : '#f59e0b'}>
                        {tip.priority} priority
                      </Badge>
                    </div>
                    <p className="tip-text">{tip.tip}</p>
                    <span className="tip-count">{tip.wrong_count} wrong answer{tip.wrong_count !== 1 ? 's' : ''}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Strong areas */}
          {insights.strong_areas?.length > 0 && (
            <Card>
              <div className="card-title">Strong Areas</div>
              <div className="strong-list">
                {insights.strong_areas.map(s => (
                  <div key={s.concept} className="strong-row">
                    <span>✓ {s.concept}</span>
                    <Badge color="#10b981">{(s.correct_rate * 100).toFixed(0)}% correct ({s.total} attempts)</Badge>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {!insights.top_weaknesses?.length && (
            <EmptyState icon="✓" title="No weaknesses yet!" description="Complete some quizzes and I'll track your trouble spots." />
          )}
        </div>
      )}

      {/* ── Concepts Tab ── */}
      {tab === 'concepts' && concepts && (
        <div className="tab-content">
          {concepts.concepts_tracked === 0 ? (
            <EmptyState icon="◉" title="No concepts tracked yet" description="Submit quizzes to see per-concept analysis." />
          ) : (
            <Card>
              <div className="card-title">{concepts.concepts_tracked} Concepts Tracked</div>
              <table className="concept-table">
                <thead>
                  <tr>
                    <th>Concept</th>
                    <th>Correct</th>
                    <th>Wrong</th>
                    <th>Wrong Rate</th>
                    <th>Health</th>
                  </tr>
                </thead>
                <tbody>
                  {concepts.concepts
                    .sort((a, b) => b.wrong_rate - a.wrong_rate)
                    .map(c => (
                      <tr key={c.concept}>
                        <td className="concept-name">{c.concept}</td>
                        <td className="correct-count">✓ {c.correct}</td>
                        <td className="wrong-count">✕ {c.wrong}</td>
                        <td>{(c.wrong_rate * 100).toFixed(0)}%</td>
                        <td>
                          <div className="mini-bar-wrap">
                            <div
                              className="mini-bar"
                              style={{
                                width: `${(1 - c.wrong_rate) * 100}%`,
                                backgroundColor: c.wrong_rate > 0.6 ? '#ef4444' : c.wrong_rate > 0.3 ? '#f59e0b' : '#10b981',
                              }}
                            />
                          </div>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </Card>
          )}
        </div>
      )}

      {/* ── Log Tab ── */}
      {tab === 'log' && log && (
        <div className="tab-content">
          {log.returned === 0 ? (
            <EmptyState icon="📋" title="No mistakes logged yet" description="Wrong answers will appear here after you attempt quizzes." />
          ) : (
            <Card>
              <div className="card-title">{log.returned} Wrong Answers</div>
              <div className="log-list">
                {log.log.map((entry, i) => (
                  <div key={i} className="log-row">
                    <span className="log-qid">{entry.question_id}</span>
                    <Badge color={difficultyColor(entry.difficulty)}>{entry.difficulty}</Badge>
                    <span className="log-topic">{entry.topic}</span>
                    <span className="log-unit">{entry.unit_id?.replace('UNIT', 'U').replace(/_/g, ' ')}</span>
                    <span className="log-time">{new Date(entry.timestamp * 1000).toLocaleDateString()}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

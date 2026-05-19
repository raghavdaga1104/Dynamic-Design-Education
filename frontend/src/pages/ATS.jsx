// pages/ATS.jsx
// ─────────────────────────────────────────────────────────────
// Resume ATS analyzer. User pastes resume + job description.
// Backend scores and returns matched/missing keywords, tips.
// ─────────────────────────────────────────────────────────────

import { useState } from 'react';
import { useApp } from '../context/AppContext';
import { ats as atsApi } from '../services/api';
import { Card, Button, Alert, Badge, Spinner, ProgressBar } from '../components/ui';

export default function ATS() {
  const { userId } = useApp();

  const [resumeText, setResumeText] = useState('');
  const [jobDesc, setJobDesc]       = useState('');
  const [targetRole, setTargetRole] = useState('');
  const [result, setResult]         = useState(null);
  const [improved, setImproved]     = useState(null);
  const [loading, setLoading]       = useState(false);
  const [loadingImprove, setLoadingImprove] = useState(false);
  const [error, setError]           = useState('');

  async function handleAnalyze() {
    if (!resumeText.trim() || !jobDesc.trim()) {
      setError('Please paste both your resume and the job description.');
      return;
    }
    setLoading(true);
    setError('');
    setResult(null);
    setImproved(null);
    try {
      const data = await atsApi.analyze(userId, resumeText, jobDesc);
      setResult(data);
    } catch (e) {
      setError('Analysis failed: ' + e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleImprove() {
    setLoadingImprove(true);
    setError('');
    try {
      const data = await atsApi.improve(userId, resumeText, jobDesc, targetRole);
      setImproved(data);
    } catch (e) {
      setError('Improvement failed: ' + e.message);
    } finally {
      setLoadingImprove(false);
    }
  }

  const scoreColor = (s) => s >= 80 ? '#10b981' : s >= 60 ? '#f59e0b' : '#ef4444';

  return (
    <div className="page ats-page">
      <div className="page-header">
        <h1 className="page-title">ATS Resume Analyzer</h1>
        <p className="page-subtitle">
          Paste your resume and a job description. The AI will score your ATS compatibility
          and show you exactly what keywords you're missing.
        </p>
      </div>

      {error && <Alert type="error">{error}</Alert>}

      {/* Input Section */}
      <div className="ats-input-grid">
        <div className="ats-input-col">
          <label className="form-label">Your Resume</label>
          <textarea
            className="textarea"
            placeholder="Paste your resume text here…"
            value={resumeText}
            onChange={e => setResumeText(e.target.value)}
            rows={12}
          />
        </div>
        <div className="ats-input-col">
          <label className="form-label">Job Description</label>
          <textarea
            className="textarea"
            placeholder="Paste the job description here…"
            value={jobDesc}
            onChange={e => setJobDesc(e.target.value)}
            rows={12}
          />
        </div>
      </div>

      <div className="ats-actions">
        <Button size="lg" onClick={handleAnalyze} loading={loading}>
          Analyze ATS Score
        </Button>
      </div>

      {/* Results */}
      {result && (
        <div className="ats-results">
          {/* Score card */}
          <Card className="ats-score-card">
            <div className="ats-score-circle" style={{ '--score-color': scoreColor(result.score_ats) }}>
              <span className="score-num">{result.score_ats}</span>
              <span className="score-max">/100</span>
            </div>
            <div className="ats-score-info">
              <h2>ATS Score</h2>
              <p className="ats-score-verdict">
                {result.score_ats >= 80 ? '✓ Strong match — good chance of passing ATS filter.'
                  : result.score_ats >= 60 ? '⚠ Moderate match — add missing keywords to improve.'
                  : '✕ Weak match — significant keyword gaps found.'}
              </p>
              <ProgressBar
                value={result.score_ats}
                max={100}
                color={scoreColor(result.score_ats)}
                showPercent={false}
              />
            </div>
          </Card>

          {/* Keywords */}
          <div className="ats-keywords-grid">
            <Card>
              <div className="card-title">✓ Matched Keywords ({result.matched_keywords?.length})</div>
              <div className="keyword-list">
                {result.matched_keywords?.map(kw => (
                  <Badge key={kw} color="#10b981">{kw}</Badge>
                ))}
                {!result.matched_keywords?.length && <p className="muted">None matched</p>}
              </div>
            </Card>

            <Card>
              <div className="card-title">✕ Missing Keywords ({result.missing_keywords?.length})</div>
              <div className="keyword-list">
                {result.missing_keywords?.map(kw => (
                  <Badge key={kw} color="#ef4444">{kw}</Badge>
                ))}
                {!result.missing_keywords?.length && <p className="muted">None missing — great!</p>}
              </div>
            </Card>
          </div>

          {/* Recommendations */}
          {result.recommendations?.length > 0 && (
            <Card>
              <div className="card-title">Recommendations</div>
              <ul className="rec-list">
                {result.recommendations.map((r, i) => (
                  <li key={i} className="rec-item">
                    <span className="rec-bullet">→</span> {r}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Improve section */}
          <Card className="ats-improve-card">
            <div className="card-title">AI-Powered Improvement (slow — uses LLM)</div>
            <div className="improve-row">
              <input
                className="input"
                placeholder="Target role (e.g. Backend Engineer)"
                value={targetRole}
                onChange={e => setTargetRole(e.target.value)}
              />
              <Button onClick={handleImprove} loading={loadingImprove} variant="secondary">
                Get Bullet Rewrites
              </Button>
            </div>
            {loadingImprove && <Spinner message="AI is rewriting your bullets… (10–60s)" />}
          </Card>

          {/* Improved output */}
          {improved && (
            <Card>
              <div className="card-title">Improved Version</div>
              {improved.bullet_rewrites?.map((br, i) => (
                <div key={i} className="bullet-rewrite">
                  <div className="bullet-before">
                    <span className="bullet-label">Before</span>
                    <p>{br.original}</p>
                  </div>
                  <div className="bullet-arrow">→</div>
                  <div className="bullet-after">
                    <span className="bullet-label">After</span>
                    <p>{br.rewritten}</p>
                  </div>
                </div>
              ))}
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

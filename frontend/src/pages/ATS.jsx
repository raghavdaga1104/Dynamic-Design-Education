// pages/ATS.jsx
// ─────────────────────────────────────────────────────────────
// Resume ATS analyzer. User drag-and-drops a resume + pastes a job description.
// Backend scores and returns matched/missing keywords, tips.
//
// Dropzone styling is inline (dzStyles below) so it matches the app's dark
// theme out of the box — no separate CSS file needed.
//
// ADD TO services/api.js, inside the `ats` export:
//   uploadResume: async (file) => {
//     const formData = new FormData();
//     formData.append('file', file);
//     const res = await fetch(`${BASE_URL}/ats/upload-resume`, { method: 'POST', body: formData });
//     if (!res.ok) throw new Error((await res.json()).detail || 'Upload failed');
//     return res.json();
//   },
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

  const [uploadedFileName, setUploadedFileName] = useState('');
  const [parsingFile, setParsingFile]           = useState(false);
  const [isDragging, setIsDragging]             = useState(false);

  async function handleResumeFile(file) {
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'docx'].includes(ext)) {
      setError('Please upload a PDF or DOCX file.');
      return;
    }
    setParsingFile(true);
    setError('');
    try {
      const data = await atsApi.uploadResume(file);
      setResumeText(data.resume_text);
      setUploadedFileName(file.name);
    } catch (e) {
      setError('Could not read that file: ' + e.message);
    } finally {
      setParsingFile(false);
    }
  }

  function handleDrop(e) {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    handleResumeFile(file);
  }

  function handleDragOver(e) {
    e.preventDefault();
    setIsDragging(true);
  }

  function handleDragLeave() {
    setIsDragging(false);
  }

  function handleFileInputChange(e) {
    handleResumeFile(e.target.files?.[0]);
  }

  const dzStyles = {
    box: {
      border: `2px dashed ${isDragging ? '#818cf8' : '#2e3548'}`,
      borderRadius: 12,
      padding: '32px 24px',
      textAlign: 'center',
      background: isDragging ? 'rgba(99,102,241,0.08)' : '#11151f',
      transition: 'all .15s ease',
    },
    button: {
      background: '#6366f1',
      color: '#fff',
      border: 'none',
      padding: '13px 30px',
      borderRadius: 8,
      fontSize: 15,
      fontWeight: 700,
      cursor: 'pointer',
      boxShadow: '0 4px 12px rgba(99,102,241,0.3)',
    },
    hint: {
      color: '#7c8398',
      fontSize: 14,
      margin: '14px 0 0',
    },
    filenameRow: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 14,
    },
    filename: {
      fontSize: 14,
      margin: 0,
      fontWeight: 500,
      color: '#e2e4ed',
    },
    remove: {
      fontSize: 12,
      color: '#f87171',
      background: 'none',
      border: 'none',
      cursor: 'pointer',
      textDecoration: 'underline',
      padding: 0,
    },
  };

  async function handleAnalyze() {
    if (!resumeText.trim() || !jobDesc.trim()) {
      setError('Please upload your resume and paste the job description.');
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

          <div
            style={dzStyles.box}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
          >
            <input
              id="ats-file-input"
              type="file"
              accept=".pdf,.docx"
              style={{ display: 'none' }}
              onChange={handleFileInputChange}
            />
            {parsingFile ? (
              <Spinner message="Reading your resume…" />
            ) : uploadedFileName ? (
              <div style={dzStyles.filenameRow}>
                <p style={dzStyles.filename}>📄 {uploadedFileName}</p>
                <button
                  type="button"
                  style={dzStyles.remove}
                  onClick={() => { setUploadedFileName(''); setResumeText(''); }}
                >
                  Remove
                </button>
              </div>
            ) : (
              <>
                <button
                  type="button"
                  style={dzStyles.button}
                  onClick={() => document.getElementById('ats-file-input').click()}
                >
                  Select Resume File
                </button>
                <p style={dzStyles.hint}>or drop a PDF / WORD document here</p>
              </>
            )}
          </div>
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
            <div className="card-title">AI-Powered Summary Improvement (slow — uses LLM)</div>
            <div className="improve-row">
              <input
                className="input"
                placeholder="Target role (e.g. Backend Engineer)"
                value={targetRole}
                onChange={e => setTargetRole(e.target.value)}
              />
              <Button onClick={handleImprove} loading={loadingImprove} variant="secondary">
                Improve Summary
              </Button>
            </div>
            {loadingImprove && <Spinner message="AI is improving your summary… (10–30s)" />}
          </Card>

          {/* Improved output */}
          {improved && (
            <Card>
              <div className="card-title">Improved Version</div>

              {/* Improved Summary */}
              {improved.improved_summary?.improved_summary && (
                <div style={{ marginBottom: 24 }}>
                  <div className="bullet-label" style={{ marginBottom: 8, fontSize: 13, color: '#7c8398', textTransform: 'uppercase', letterSpacing: 1 }}>
                    Improved Professional Summary
                  </div>
                  <p style={{ color: '#e2e4ed', lineHeight: 1.7, margin: 0 }}>
                    {improved.improved_summary.improved_summary}
                  </p>
                  {improved.improved_summary.changes_made && (
                    <p style={{ color: '#7c8398', fontSize: 13, marginTop: 10, fontStyle: 'italic' }}>
                      ✎ {improved.improved_summary.changes_made}
                    </p>
                  )}
                </div>
              )}

              {/* Keyword suggestions if any */}
              {improved.keyword_suggestions?.filter(s => s.can_add).length > 0 && (
                <div>
                  <div className="bullet-label" style={{ marginBottom: 8, fontSize: 13, color: '#7c8398', textTransform: 'uppercase', letterSpacing: 1 }}>
                    Keyword Addition Suggestions
                  </div>
                  {improved.keyword_suggestions.filter(s => s.can_add).map((s, i) => (
                    <div key={i} style={{ marginBottom: 10, padding: '10px 14px', background: '#1a1f2e', borderRadius: 8, borderLeft: '3px solid #6366f1' }}>
                      <span style={{ color: '#818cf8', fontWeight: 600, fontSize: 13 }}>{s.keyword}</span>
                      <span style={{ color: '#7c8398', fontSize: 13 }}> → {s.section}</span>
                      <p style={{ color: '#e2e4ed', fontSize: 14, margin: '6px 0 0' }}>{s.suggestion}</p>
                    </div>
                  ))}
                </div>
              )}

              {improved.anti_hallucination_note && (
                <p style={{ color: '#4b5563', fontSize: 12, marginTop: 16, fontStyle: 'italic' }}>
                  ℹ {improved.anti_hallucination_note}
                </p>
              )}
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
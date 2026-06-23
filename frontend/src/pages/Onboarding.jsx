// pages/Onboarding.jsx

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { Button, Alert } from '../components/ui';
import { generateUserId } from '../utils/helpers';

const DEGREES = ['BTech', 'BSc', 'BCA', 'MCA', 'MTech', 'MSc', 'Other'];
const YEARS   = ['1st', '2nd', '3rd', '4th', 'Postgrad'];

export default function Onboarding() {
const { setUserId, setProfile, diagnosticDone, serverStatus } = useApp();
const navigate = useNavigate();

const [step, setStep] = useState(1);
const [inputId, setInputId] = useState('');
const [form, setForm] = useState({
degree: 'BTech',
year: '2nd'
});
const [error, setError] = useState('');

function handleIdSubmit() {
const trimmed = inputId.trim();

```
if (!trimmed) {
  setError('Please enter a user ID.');
  return;
}

setError('');
setUserId(trimmed);
setStep(2);
```

}

function handleAutoId() {
const id = generateUserId();
setInputId(id);
}

function handleProfileSubmit() {
setProfile(form);
navigate(diagnosticDone ? '/dashboard' : '/select-subject');
}

return ( <div className="onboard-page">
{/* Background decoration */} <div className="onboard-bg"> <div className="bg-circle bg-circle-1" /> <div className="bg-circle bg-circle-2" /> <div className="bg-grid" /> </div>

```
  <div className="onboard-content">
    {/* Header */}
    <div className="onboard-header">
      <div className="onboard-logo">DDE</div>

      <h1 className="onboard-title">
        Dynamic
        <br />
        Design
        <br />
        Education
      </h1>

      <p className="onboard-subtitle">
        AI-powered adaptive learning — personalised to your pace,
        goals, and gaps.
      </p>
    </div>

    {/* Card */}
    <div className="onboard-card">
      {serverStatus === 'error' && (
        <Alert type="error" title="Server offline">
          Backend is not responding. Make sure the DDE API is running on port 8000.
        </Alert>
      )}

      {/* Step 1 */}
      {step === 1 && (
        <div className="onboard-step">
          <h2 className="step-title">Who are you?</h2>

          <p className="step-desc">
            Enter your student ID or any unique name to get started.
          </p>

          <div className="input-row">
            <input
              className="input"
              type="text"
              placeholder="e.g. john_doe_2024"
              value={inputId}
              onChange={e => setInputId(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleIdSubmit()}
              autoFocus
            />

            <Button variant="ghost" size="sm" onClick={handleAutoId}>
              Auto
            </Button>
          </div>

          {error && <p className="input-error">{error}</p>}

          <Button
            onClick={handleIdSubmit}
            className="btn-full"
            size="lg"
          >
            Continue →
          </Button>
        </div>
      )}

      {/* Step 2 */}
      {step === 2 && (
        <div className="onboard-step">
          <h2 className="step-title">Your profile</h2>

          <p className="step-desc">
            This helps the AI personalise recommendations for you.
          </p>

          <div className="form-group">
            <label className="form-label">Degree</label>

            <div className="chip-group">
              {DEGREES.map(d => (
                <button
                  key={d}
                  className={`chip ${
                    form.degree === d ? 'chip-active' : ''
                  }`}
                  onClick={() =>
                    setForm(f => ({
                      ...f,
                      degree: d
                    }))
                  }
                >
                  {d}
                </button>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Year</label>

            <div className="chip-group">
              {YEARS.map(y => (
                <button
                  key={y}
                  className={`chip ${
                    form.year === y ? 'chip-active' : ''
                  }`}
                  onClick={() =>
                    setForm(f => ({
                      ...f,
                      year: y
                    }))
                  }
                >
                  {y}
                </button>
              ))}
            </div>
          </div>

          <Button
            onClick={handleProfileSubmit}
            className="btn-full"
            size="lg"
          >
            {diagnosticDone
              ? 'Go to Dashboard →'
              : 'Choose Subject →'}
          </Button>

          <button
            className="back-link"
            onClick={() => setStep(1)}
          >
            ← Change ID
          </button>
        </div>
      )}
    </div>

    {/* Feature highlights */}
    <div className="onboard-features">
      {[
        { icon: '⚙', label: 'MCTS AI Recommendations' },
        { icon: '◈', label: 'BKT + IRT Scoring' },
        { icon: '⬜', label: 'SM-2 Spaced Repetition' },
        { icon: '◉', label: 'RAG Chatbot Tutor' },
      ].map(f => (
        <div key={f.label} className="feature-chip">
          <span>{f.icon}</span> {f.label}
        </div>
      ))}
    </div>
  </div>
</div>
);
}

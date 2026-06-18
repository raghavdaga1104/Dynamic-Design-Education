// pages/Signup.jsx — redesigned to match new auth layout
import { useState, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { auth } from '../services/api';

const DEGREES   = ['BTech', 'BSc', 'BCA', 'MCA', 'MTech', 'MSc', 'Other'];
const YEARS     = ['1st', '2nd', '3rd', '4th', 'Postgrad'];
const INTERESTS = ['python', 'data structures', 'oop', 'algorithms'];

function NeuralCanvas() {
  const canvasRef = useRef(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    let animId;
    const resize = () => { canvas.width = canvas.offsetWidth; canvas.height = canvas.offsetHeight; };
    resize();
    window.addEventListener('resize', resize);
    const nodes = Array.from({ length: 38 }, () => ({
      x: Math.random() * canvas.width, y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.4, vy: (Math.random() - 0.5) * 0.4,
      r: Math.random() * 2.5 + 1, pulse: Math.random() * Math.PI * 2,
    }));
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      nodes.forEach(n => {
        n.x += n.vx; n.y += n.vy; n.pulse += 0.018;
        if (n.x < 0 || n.x > canvas.width) n.vx *= -1;
        if (n.y < 0 || n.y > canvas.height) n.vy *= -1;
      });
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x, dy = nodes[i].y - nodes[j].y;
          const dist = Math.sqrt(dx*dx + dy*dy);
          if (dist < 130) {
            ctx.beginPath(); ctx.moveTo(nodes[i].x, nodes[i].y); ctx.lineTo(nodes[j].x, nodes[j].y);
            ctx.strokeStyle = `rgba(108,126,255,${(1 - dist/130) * 0.25})`; ctx.lineWidth = 0.8; ctx.stroke();
          }
        }
      }
      nodes.forEach(n => {
        const glow = Math.sin(n.pulse) * 0.5 + 0.5;
        ctx.beginPath(); ctx.arc(n.x, n.y, n.r + glow, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(108,126,255,${0.4 + glow * 0.5})`; ctx.fill();
      });
      animId = requestAnimationFrame(draw);
    };
    draw();
    return () => { cancelAnimationFrame(animId); window.removeEventListener('resize', resize); };
  }, []);
  return <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />;
}

export default function Signup() {
  const { setUserId, setUserName, setProfile } = useApp();
  const navigate = useNavigate();

  const [step, setStep]         = useState(1);
  const [account, setAccount]   = useState({ name: '', email: '', password: '', confirm: '' });
  const [profile, setProfileSt] = useState({ degree: 'BTech', year: '2nd', interest: 'python' });
  const [error, setError]       = useState('');
  const [loading, setLoading]   = useState(false);
  const [mounted, setMounted]   = useState(false);

  useEffect(() => { setTimeout(() => setMounted(true), 50); }, []);

  function handleAccountChange(e) { setAccount(a => ({ ...a, [e.target.name]: e.target.value })); if (error) setError(''); }

  function handleNext() {
    const { name, email, password, confirm } = account;
    if (!name.trim())    return setError('Full name is required.');
    if (!email.trim())   return setError('Email is required.');
    if (!/\S+@\S+\.\S+/.test(email)) return setError('Enter a valid email address.');
    if (password.length < 8) return setError('Password must be at least 8 characters.');
    if (password !== confirm) return setError('Passwords do not match.');
    setError(''); setStep(2);
  }

  async function handleSubmit() {
    setError(''); setLoading(true);
    try {
      const data = await auth.signup({ name: account.name.trim(), email: account.email.trim(), password: account.password, ...profile });
      setUserId(data.user_id);
      setUserName(data.name || data.user_id);
      setProfile(profile);
      navigate('/diagnostic');
    } catch (err) {
      setError(err.message || 'Registration failed. Please try again.');
    } finally { setLoading(false); }
  }

  const steps = [
    { label: 'Account', num: 1 },
    { label: 'Profile', num: 2 },
  ];

  return (
    <div className="auth-page">
      {/* Left panel */}
      <div className={`auth-left ${mounted ? 'auth-in' : ''}`}>
        <div className="auth-canvas-wrap"><NeuralCanvas /></div>
        <div className="auth-left-content">
          <div className="auth-brand">
            <span className="auth-brand-mark">DDE</span>
            <span className="auth-brand-name">Dynamic Design Education</span>
          </div>
          <div className="auth-hero">
            <h1 className="auth-hero-title">Your personal<br />AI tutor awaits.</h1>
            <p className="auth-hero-sub">
              Answer a quick placement test and DDE's AI will build a learning path tailored exactly to you.
            </p>
          </div>
          <div className="auth-stats">
            {[
              { value: '14',   label: 'Learning Units'    },
              { value: 'MCTS', label: 'AI Pathfinding'    },
              { value: 'BKT',  label: 'Knowledge Tracing' },
              { value: 'RAG',  label: 'Chatbot Tutor'     },
            ].map((s, i) => (
              <div key={s.label} className="auth-stat" style={{ animationDelay: `${0.6 + i * 0.1}s` }}>
                <span className="auth-stat-value">{s.value}</span>
                <span className="auth-stat-label">{s.label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right panel */}
      <div className={`auth-right ${mounted ? 'auth-in' : ''}`}>
        <div className="auth-form-wrap">

          {/* Step indicator */}
          <div className="auth-steps">
            {steps.map((s, i) => (
              <>
                <div key={s.num} className={`auth-step-item ${step === s.num ? 'active' : ''} ${step > s.num ? 'done' : ''}`}>
                  <div className="auth-step-dot">{step > s.num ? '✓' : s.num}</div>
                  <span className="auth-step-label">{s.label}</span>
                </div>
                {i < steps.length - 1 && (
                  <div className="auth-step-connector">
                    <div className="auth-step-connector-fill" style={{ width: step > 1 ? '100%' : '0%' }} />
                  </div>
                )}
              </>
            ))}
          </div>

          <div className="auth-form-header">
            <h2 className="auth-form-title">{step === 1 ? 'Create account' : 'Your profile'}</h2>
            <p className="auth-form-sub">{step === 1 ? 'Join thousands of learners on DDE' : 'Helps AI personalise your path'}</p>
          </div>

          {error && (
            <div className="auth-error">
              <span className="auth-error-icon">!</span>
              {error}
            </div>
          )}

          {step === 1 && (
            <>
              <div className="auth-fields">
                <div className="auth-field">
                  <label className="auth-label">Full Name</label>
                  <input className="auth-input" type="text" name="name" placeholder="Arjun Sharma"
                    value={account.name} onChange={handleAccountChange} autoFocus autoComplete="name" />
                </div>
                <div className="auth-field">
                  <label className="auth-label">Email</label>
                  <input className="auth-input" type="email" name="email" placeholder="you@example.com"
                    value={account.email} onChange={handleAccountChange} autoComplete="email" />
                </div>
                <div className="auth-field">
                  <label className="auth-label">Password</label>
                  <input className="auth-input" type="password" name="password" placeholder="Min. 8 characters"
                    value={account.password} onChange={handleAccountChange} autoComplete="new-password" />
                </div>
                <div className="auth-field">
                  <label className="auth-label">Confirm Password</label>
                  <input className="auth-input" type="password" name="confirm" placeholder="Repeat password"
                    value={account.confirm} onChange={handleAccountChange}
                    onKeyDown={e => e.key === 'Enter' && handleNext()} autoComplete="new-password" />
                </div>
              </div>
              <button className="auth-btn" onClick={handleNext}>Next →</button>
              <p className="auth-switch">Already have an account? <Link to="/login" className="auth-link">Sign in</Link></p>
            </>
          )}

          {step === 2 && (
            <>
              <div className="auth-fields">
                <div className="auth-field">
                  <label className="auth-label">Degree</label>
                  <div className="auth-chip-group">
                    {DEGREES.map(d => (
                      <button key={d} className={`auth-chip ${profile.degree === d ? 'active' : ''}`}
                        onClick={() => setProfileSt(p => ({ ...p, degree: d }))}>{d}</button>
                    ))}
                  </div>
                </div>
                <div className="auth-field">
                  <label className="auth-label">Year</label>
                  <div className="auth-chip-group">
                    {YEARS.map(y => (
                      <button key={y} className={`auth-chip ${profile.year === y ? 'active' : ''}`}
                        onClick={() => setProfileSt(p => ({ ...p, year: y }))}>{y}</button>
                    ))}
                  </div>
                </div>
                <div className="auth-field">
                  <label className="auth-label">Primary Interest</label>
                  <div className="auth-chip-group">
                    {INTERESTS.map(i => (
                      <button key={i} className={`auth-chip ${profile.interest === i ? 'active' : ''}`}
                        onClick={() => setProfileSt(p => ({ ...p, interest: i }))}>{i}</button>
                    ))}
                  </div>
                </div>
              </div>
              <button className={`auth-btn ${loading ? 'auth-btn-loading' : ''}`} onClick={handleSubmit} disabled={loading}>
                {loading ? <span className="auth-spinner" /> : 'Create Account →'}
              </button>
              <button className="auth-back" onClick={() => { setStep(1); setError(''); }}>← Back</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
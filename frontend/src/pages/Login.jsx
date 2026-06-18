// pages/Login.jsx — redesigned
import { useState, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { auth } from '../services/api';

// ── Animated canvas background ────────────────────────────────
function NeuralCanvas() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    let animId;

    const resize = () => {
      canvas.width  = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    // Nodes
    const NODE_COUNT = 38;
    const nodes = Array.from({ length: NODE_COUNT }, () => ({
      x:   Math.random() * canvas.width,
      y:   Math.random() * canvas.height,
      vx:  (Math.random() - 0.5) * 0.4,
      vy:  (Math.random() - 0.5) * 0.4,
      r:   Math.random() * 2.5 + 1,
      pulse: Math.random() * Math.PI * 2,
    }));

    const CONNECT_DIST = 130;

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Move nodes
      nodes.forEach(n => {
        n.x += n.vx; n.y += n.vy; n.pulse += 0.018;
        if (n.x < 0 || n.x > canvas.width)  n.vx *= -1;
        if (n.y < 0 || n.y > canvas.height) n.vy *= -1;
      });

      // Edges
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < CONNECT_DIST) {
            const alpha = (1 - dist / CONNECT_DIST) * 0.25;
            ctx.beginPath();
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(nodes[j].x, nodes[j].y);
            ctx.strokeStyle = `rgba(108,126,255,${alpha})`;
            ctx.lineWidth = 0.8;
            ctx.stroke();
          }
        }
      }

      // Nodes
      nodes.forEach(n => {
        const glow = Math.sin(n.pulse) * 0.5 + 0.5;
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r + glow, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(108,126,255,${0.4 + glow * 0.5})`;
        ctx.fill();
      });

      animId = requestAnimationFrame(draw);
    };
    draw();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />;
}

// ── Stats shown on the left panel ─────────────────────────────
const STATS = [
  { value: '14',    label: 'Learning Units'       },
  { value: 'MCTS',  label: 'AI Recommendation'    },
  { value: 'IRT',   label: 'Adaptive Scoring'     },
  { value: 'SM-2',  label: 'Spaced Repetition'    },
];

// ── Main component ─────────────────────────────────────────────
export default function Login() {
  const { setUserId, setUserName, setProfile } = useApp();
  const navigate = useNavigate();

  const [form, setForm]       = useState({ email: '', password: '' });
  const [error, setError]     = useState('');
  const [loading, setLoading] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setTimeout(() => setMounted(true), 50); }, []);

  function handleChange(e) {
    setForm(f => ({ ...f, [e.target.name]: e.target.value }));
    if (error) setError('');
  }

  async function handleSubmit() {
    const { email, password } = form;
    if (!email.trim()) { setError('Email is required.'); return; }
    if (!password)      { setError('Password is required.'); return; }
    setError(''); setLoading(true);
    try {
      const data = await auth.login(email.trim(), password);
      setUserId(data.user_id);
      setUserName(data.name || data.user_id);
      if (data.profile) setProfile(data.profile);
      navigate(data.is_new_user ? '/diagnostic' : '/dashboard');
    } catch (err) {
      setError(err.message || 'Invalid email or password.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      {/* ── Left panel ── */}
      <div className={`auth-left ${mounted ? 'auth-in' : ''}`}>
        <div className="auth-canvas-wrap">
          <NeuralCanvas />
        </div>

        {/* Overlay content */}
        <div className="auth-left-content">
          <div className="auth-brand">
            <span className="auth-brand-mark">DDE</span>
            <span className="auth-brand-name">Dynamic Design Education</span>
          </div>

          <div className="auth-hero">
            <h1 className="auth-hero-title">Learn smarter.<br />Not harder.</h1>
            <p className="auth-hero-sub">
              AI-powered adaptive learning that finds your gaps, fixes them, and keeps you moving.
            </p>
          </div>

          <div className="auth-stats">
            {STATS.map((s, i) => (
              <div key={s.label} className="auth-stat" style={{ animationDelay: `${0.6 + i * 0.1}s` }}>
                <span className="auth-stat-value">{s.value}</span>
                <span className="auth-stat-label">{s.label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Right panel ── */}
      <div className={`auth-right ${mounted ? 'auth-in' : ''}`}>
        <div className="auth-form-wrap">

          <div className="auth-form-header">
            <h2 className="auth-form-title">Welcome back</h2>
            <p className="auth-form-sub">Sign in to continue your journey</p>
          </div>

          {error && (
            <div className="auth-error">
              <span className="auth-error-icon">!</span>
              {error}
            </div>
          )}

          <div className="auth-fields">
            <div className="auth-field">
              <label className="auth-label">Email</label>
              <input
                className={`auth-input ${error ? 'auth-input-err' : ''}`}
                type="email" name="email"
                placeholder="you@example.com"
                value={form.email}
                onChange={handleChange}
                onKeyDown={e => e.key === 'Enter' && handleSubmit()}
                autoFocus autoComplete="email"
              />
            </div>

            <div className="auth-field">
              <label className="auth-label">Password</label>
              <input
                className={`auth-input ${error ? 'auth-input-err' : ''}`}
                type="password" name="password"
                placeholder="••••••••"
                value={form.password}
                onChange={handleChange}
                onKeyDown={e => e.key === 'Enter' && handleSubmit()}
                autoComplete="current-password"
              />
            </div>
          </div>

          <button
            className={`auth-btn ${loading ? 'auth-btn-loading' : ''}`}
            onClick={handleSubmit}
            disabled={loading}
          >
            {loading ? <span className="auth-spinner" /> : 'Sign in →'}
          </button>

          <p className="auth-switch">
            New to DDE?{' '}
            <Link to="/signup" className="auth-link">Create a free account</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
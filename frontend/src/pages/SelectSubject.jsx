// pages/SelectSubject.jsx
// ─────────────────────────────────────────────────────────────
// Subject selection screen shown after signup/onboarding,
// before the Placement Test.
// ─────────────────────────────────────────────────────────────

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';

const SUBJECTS = [
  {
    id: 'dsa-python',
    title: 'Data Structures & Algorithms',
    subtitle: 'with Python',
    icon: '🧩',
    description: 'Arrays, trees, graphs, sorting, dynamic programming & more — implemented in Python.',
    tags: ['Arrays', 'Trees', 'Graphs', 'DP', 'Sorting'],
    locked: false,
  },
  {
    id: 'python',
    title: 'Python',
    subtitle: 'Future Scope',
    icon: '🐍',
    description: 'Core Python, OOP, file I/O, libraries, and real-world projects.',
    tags: ['OOP', 'Libraries', 'Projects'],
    locked: true,
  },
  {
    id: 'prog-fundamentals',
    title: 'Programming Fundamentals',
    subtitle: 'Future Scope',
    icon: '💻',
    description: 'Variables, control flow, functions, and the building blocks of every language.',
    tags: ['Logic', 'Control Flow', 'Functions'],
    locked: true,
  },
  {
    id: 'dbms',
    title: 'Database Management Systems',
    subtitle: 'Future Scope',
    icon: '🗄️',
    description: 'Relational models, SQL, normalization, transactions, and indexing.',
    tags: ['SQL', 'Normalization', 'ER Models'],
    locked: true,
  },
  {
    id: 'os',
    title: 'Operating Systems',
    subtitle: 'Future Scope',
    icon: '⚙️',
    description: 'Processes, memory management, scheduling, and concurrency.',
    tags: ['Processes', 'Memory', 'Scheduling'],
    locked: true,
  },
  {
    id: 'coming-soon',
    title: 'More subjects',
    subtitle: 'coming soon',
    icon: '🚀',
    description: 'Computer Networks, Machine Learning, System Design, and more.',
    tags: [],
    locked: true,
    isPlaceholder: true,
  },
];

export default function SelectSubject() {
  const { setProfile, profile, diagnosticDone } = useApp();
  const navigate = useNavigate();
  const [mounted, setMounted] = useState(false);
  const [hovered, setHovered] = useState(null);

  useEffect(() => {
    setTimeout(() => setMounted(true), 50);
  }, []);

  function handleSelect(subject) {
    if (subject.locked) return;
    setProfile({ ...profile, subject: subject.id });
    navigate(diagnosticDone ? '/dashboard' : '/diagnostic');
  }

  return (
    <div className="ss-page" style={{ opacity: mounted ? 1 : 0, transition: 'opacity 0.4s ease' }}>
      {/* Background */}
      <div className="ss-bg">
        <div className="ss-bg-orb ss-bg-orb-1" />
        <div className="ss-bg-orb ss-bg-orb-2" />
      </div>

      <div className="ss-container">
        {/* Header */}
        <div className="ss-header" style={{ animationDelay: '0s' }}>
          <div className="ss-brand">DDE</div>
          <h1 className="ss-title">Choose your subject</h1>
          <p className="ss-subtitle">
            Select a subject to begin your personalised learning journey.
            More subjects will be unlocked over time.
          </p>
        </div>

        {/* Grid */}
        <div className="ss-grid">
          {SUBJECTS.map((subject, i) => (
            <div
              key={subject.id}
              className={[
                'ss-card',
                subject.locked ? 'ss-card-locked' : 'ss-card-active',
                subject.isPlaceholder ? 'ss-card-placeholder' : '',
                hovered === subject.id && !subject.locked ? 'ss-card-hovered' : '',
              ].join(' ')}
              style={{ animationDelay: `${0.1 + i * 0.07}s` }}
              onClick={() => handleSelect(subject)}
              onMouseEnter={() => setHovered(subject.id)}
              onMouseLeave={() => setHovered(null)}
              tabIndex={subject.locked ? -1 : 0}
              onKeyDown={e => e.key === 'Enter' && handleSelect(subject)}
              role="button"
              aria-disabled={subject.locked}
            >
              {/* Lock badge */}
              {subject.locked && !subject.isPlaceholder && (
                <div className="ss-lock-badge">
                  <span className="ss-lock-icon">🔒</span>
                  <span className="ss-lock-label">Coming Soon</span>
                </div>
              )}

              {/* Card body */}
              <div className="ss-card-icon">{subject.icon}</div>
              <div className="ss-card-body">
                <h2 className="ss-card-title">{subject.title}</h2>
                <span className={`ss-card-subtitle ${subject.locked ? 'ss-card-subtitle-muted' : ''}`}>
                  {subject.subtitle}
                </span>
                {!subject.isPlaceholder && (
                  <p className="ss-card-desc">{subject.description}</p>
                )}
              </div>

              {/* Tags */}
              {subject.tags.length > 0 && (
                <div className="ss-card-tags">
                  {subject.tags.map(tag => (
                    <span key={tag} className="ss-tag">{tag}</span>
                  ))}
                </div>
              )}

              {/* CTA for active */}
              {!subject.locked && (
                <div className="ss-card-cta">
                  Start Placement Test →
                </div>
              )}
            </div>
          ))}
        </div>

        <p className="ss-footer-note">
          🎯 Only <strong>Data Structures &amp; Algorithms with Python</strong> is available right now.
          Other subjects are in development.
        </p>
      </div>
    </div>
  );
}

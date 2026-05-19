// components/layout/Layout.jsx
// ─────────────────────────────────────────────────────────────
// Main app shell: sidebar + top bar + main content area.
// All authenticated pages are wrapped in this layout.
// ─────────────────────────────────────────────────────────────

import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useApp } from '../../context/AppContext';

const NAV_ITEMS = [
  { path: '/dashboard',  icon: '⬡',  label: 'Dashboard'   },
  { path: '/learn',      icon: '▶',  label: 'Learn'        },
  { path: '/skill-tree', icon: '⟡',  label: 'Skill Tree'   },
  { path: '/flashcards', icon: '⬜',  label: 'Flashcards'   },
  { path: '/mistakes',   icon: '◈',  label: 'Weak Areas'   },
  { path: '/ats',        icon: '⬙',  label: 'ATS Resume'   },
];

export default function Layout({ children }) {
  const { userId } = useApp();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className={`layout ${collapsed ? 'layout-collapsed' : ''}`}>
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="sidebar-brand" onClick={() => navigate('/dashboard')}>
          <span className="brand-mark">DDE</span>
          {!collapsed && <span className="brand-full">Dynamic Design Education</span>}
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map(item => (
            <button
              key={item.path}
              className={`nav-item ${location.pathname === item.path ? 'nav-active' : ''}`}
              onClick={() => navigate(item.path)}
            >
              <span className="nav-icon">{item.icon}</span>
              {!collapsed && <span className="nav-label">{item.label}</span>}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          {!collapsed && (
            <div className="user-chip">
              <span className="user-dot" />
              <span className="user-id">{userId}</span>
            </div>
          )}
          <button className="collapse-btn" onClick={() => setCollapsed(c => !c)}>
            {collapsed ? '→' : '←'}
          </button>
        </div>
      </aside>

      {/* ── Main Content ── */}
      <main className="main-content">
        {children}
      </main>
    </div>
  );
}

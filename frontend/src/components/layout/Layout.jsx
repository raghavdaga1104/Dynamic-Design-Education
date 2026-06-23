// components/layout/Layout.jsx
import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { auth } from '../../services/api';

const NAV_ITEMS = [
  { path: '/dashboard',  icon: '⬡', label: 'Dashboard'  },
  { path: '/learn',      icon: '▶', label: 'Learn'       },
  { path: '/skill-tree', icon: '⟡', label: 'Skill Tree'  },
  { path: '/flashcards', icon: '⬜', label: 'Flashcards'  },
  { path: '/mistakes',   icon: '◈', label: 'Weak Areas'  },
  { path: '/ats',        icon: '⬙', label: 'ATS Resume'  },
];

const SUBJECT_LABELS = {
  'dsa-python': 'DSA with Python',
};

export default function Layout({ children }) {
  const { userId, userName, profile, resetAllLocalState } = useApp();
  const navigate  = useNavigate();
  const location  = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);

  async function handleLogout() {
    try { await auth.logout(); } catch (_) {}
    resetAllLocalState();
    navigate('/login');
  }

  const initials = userName
    ? userName.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase()
    : userId.slice(0, 2).toUpperCase();

  const subjectLabel = SUBJECT_LABELS[profile?.subject] || profile?.subject || '—';

  return (
    <div className={`layout ${collapsed ? 'layout-collapsed' : ''}`}>

      {/* ── Sidebar ── */}
      <aside className="sidebar">

        {/* Brand */}
        <div className="sidebar-brand" onClick={() => navigate('/dashboard')}>
          <div className="brand-logo">
            <span>D</span>
          </div>
          {!collapsed && (
            <div className="brand-text">
              <span className="brand-title">DDE</span>
              <span className="brand-sub">Adaptive Learning</span>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav className="sidebar-nav">
          {!collapsed && <span className="nav-section-label">Menu</span>}
          {NAV_ITEMS.map(item => (
            <button
              key={item.path}
              className={`nav-item ${location.pathname === item.path ? 'nav-active' : ''}`}
              onClick={() => navigate(item.path)}
              title={collapsed ? item.label : ''}
            >
              <span className="nav-icon">{item.icon}</span>
              {!collapsed && <span className="nav-label">{item.label}</span>}
              {location.pathname === item.path && <span className="nav-pip" />}
            </button>
          ))}
        </nav>

        {/* Footer */}
        <div className="sidebar-footer">
          {/* Profile button */}
          <button
            className="sidebar-profile-btn"
            onClick={() => setProfileOpen(o => !o)}
            title="Profile"
          >
            <div className="sidebar-avatar">{initials}</div>
            {!collapsed && (
              <div className="sidebar-user-info">
                <span className="sidebar-user-name">{userName || userId}</span>
                <span className="sidebar-user-meta">{profile?.degree} · {profile?.year} Year</span>
              </div>
            )}
            {!collapsed && <span className="sidebar-chevron">{profileOpen ? '▲' : '▼'}</span>}
          </button>

          {/* Profile dropdown */}
          {profileOpen && !collapsed && (
            <div className="sidebar-profile-menu">
              <div className="profile-menu-header">
                <div className="profile-menu-avatar">{initials}</div>
                <div>
                  <div className="profile-menu-name">{userName || userId}</div>
                  <div className="profile-menu-id">{userId}</div>
                </div>
              </div>
              <div className="profile-menu-divider" />
              <div className="profile-menu-row">
                <span className="profile-menu-label">Degree</span>
                <span className="profile-menu-val">{profile?.degree}</span>
              </div>
              <div className="profile-menu-row">
                <span className="profile-menu-label">Year</span>
                <span className="profile-menu-val">{profile?.year}</span>
              </div>
              <div className="profile-menu-row">
                <span className="profile-menu-label">Subject</span>
                <span className="profile-menu-val">{subjectLabel}</span>
              </div>
              <div className="profile-menu-divider" />
              <button className="profile-menu-logout" onClick={handleLogout}>
                ⏻ &nbsp;Sign out
              </button>
            </div>
          )}

          <button
            className="collapse-btn"
            onClick={() => { setCollapsed(c => !c); setProfileOpen(false); }}
            title={collapsed ? 'Expand' : 'Collapse'}
          >
            {collapsed ? '→' : '←'}
          </button>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="main-content" onClick={() => profileOpen && setProfileOpen(false)}>
        {children}
      </main>
    </div>
  );
}
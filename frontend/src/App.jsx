// src/App.jsx
// ─────────────────────────────────────────────────────────────
// Route definitions. Guards redirect unauthenticated users
// back to login. Layout wraps all authenticated pages.
// ─────────────────────────────────────────────────────────────

import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useApp } from './context/AppContext';
import Layout from './components/layout/Layout';
import { ToastContainer } from './components/ui';

// Pages
import Onboarding  from './pages/Onboarding';
import Login       from './pages/Login';
import Signup      from './pages/Signup';
import Diagnostic  from './pages/Diagnostic';
import Dashboard   from './pages/Dashboard';
import Learn       from './pages/Learn';
import SkillTree   from './pages/SkillTree';
import Flashcards  from './pages/Flashcards';
import Mistakes    from './pages/Mistakes';
import ATS           from './pages/ATS';
import SelectSubject from './pages/SelectSubject';

// ── Auth Guard ───────────────────────────────────────────────
function RequireAuth({ children }) {
  const { userId } = useApp();
  const location = useLocation();
  if (!userId) return <Navigate to="/login" state={{ from: location }} replace />;
  return children;
}

// ── Authenticated pages wrapped in Layout ─────────────────
function AuthenticatedPage({ children }) {
  return (
    <RequireAuth>
      <Layout>{children}</Layout>
    </RequireAuth>
  );
}

export default function App() {
  return (
    <>
      <ToastContainer />
      <Routes>
        {/* Root → Login */}
        <Route path="/"           element={<Navigate to="/login" replace />} />

        {/* Public */}
        <Route path="/login"      element={<Login />} />
        <Route path="/signup"     element={<Signup />} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/diagnostic"      element={<RequireAuth><Diagnostic /></RequireAuth>} />
        <Route path="/select-subject" element={<RequireAuth><SelectSubject /></RequireAuth>} />

        {/* Authenticated + Layout */}
        <Route path="/dashboard"  element={<AuthenticatedPage><Dashboard /></AuthenticatedPage>} />
        <Route path="/learn"      element={<AuthenticatedPage><Learn /></AuthenticatedPage>} />
        <Route path="/skill-tree" element={<AuthenticatedPage><SkillTree /></AuthenticatedPage>} />
        <Route path="/flashcards" element={<AuthenticatedPage><Flashcards /></AuthenticatedPage>} />
        <Route path="/mistakes"   element={<AuthenticatedPage><Mistakes /></AuthenticatedPage>} />
        <Route path="/ats"        element={<AuthenticatedPage><ATS /></AuthenticatedPage>} />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </>
  );
}
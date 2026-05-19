// context/AppContext.jsx
// ─────────────────────────────────────────────────────────────
// Global state for userId, learner profile, and health status.
// Wraps the entire app so any component can access shared data.
// ─────────────────────────────────────────────────────────────

import { createContext, useContext, useState, useEffect } from 'react';
import { health as healthApi } from '../services/api';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [userId, setUserId] = useState(() => localStorage.getItem('dde_user_id') || '');
  const [profile, setProfile] = useState(() => {
    const saved = localStorage.getItem('dde_profile');
    return saved ? JSON.parse(saved) : { degree: 'BTech', year: '2nd', interest: 'python' };
  });
  const [serverStatus, setServerStatus] = useState('checking'); // 'ok' | 'error' | 'checking'
  const [diagnosticDone, setDiagnosticDone] = useState(
    () => localStorage.getItem('dde_diagnostic_done') === 'true'
  );

  // Save userId to localStorage whenever it changes
  useEffect(() => {
    if (userId) localStorage.setItem('dde_user_id', userId);
  }, [userId]);

  // Save profile to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem('dde_profile', JSON.stringify(profile));
  }, [profile]);

  // Check server health on mount
  useEffect(() => {
    healthApi.check()
      .then(() => setServerStatus('ok'))
      .catch(() => setServerStatus('error'));
  }, []);

  function markDiagnosticDone() {
    setDiagnosticDone(true);
    localStorage.setItem('dde_diagnostic_done', 'true');
  }

  function resetAllLocalState() {
    localStorage.removeItem('dde_user_id');
    localStorage.removeItem('dde_profile');
    localStorage.removeItem('dde_diagnostic_done');
    setUserId('');
    setDiagnosticDone(false);
    setProfile({ degree: 'BTech', year: '2nd', interest: 'python' });
  }

  return (
    <AppContext.Provider value={{
      userId, setUserId,
      profile, setProfile,
      serverStatus,
      diagnosticDone, markDiagnosticDone,
      resetAllLocalState,
    }}>
      {children}
    </AppContext.Provider>
  );
}

// Custom hook — use this instead of useContext(AppContext) directly
export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used inside AppProvider');
  return ctx;
}

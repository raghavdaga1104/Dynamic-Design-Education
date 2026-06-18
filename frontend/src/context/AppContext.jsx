// context/AppContext.jsx
import { createContext, useContext, useState, useEffect } from 'react';
import { health as healthApi } from '../services/api';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [userId, setUserId]   = useState(() => localStorage.getItem('dde_user_id') || '');
  const [userName, setUserName] = useState(() => localStorage.getItem('dde_user_name') || '');
  const [profile, setProfile] = useState(() => {
    const saved = localStorage.getItem('dde_profile');
    return saved ? JSON.parse(saved) : { degree: 'BTech', year: '2nd', interest: 'python' };
  });
  const [serverStatus, setServerStatus] = useState('checking');
  const [diagnosticDone, setDiagnosticDone] = useState(
    () => localStorage.getItem('dde_diagnostic_done') === 'true'
  );

  useEffect(() => {
    if (userId) localStorage.setItem('dde_user_id', userId);
  }, [userId]);

  useEffect(() => {
    if (userName) localStorage.setItem('dde_user_name', userName);
  }, [userName]);

  useEffect(() => {
    localStorage.setItem('dde_profile', JSON.stringify(profile));
  }, [profile]);

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
    localStorage.removeItem('dde_user_name');
    localStorage.removeItem('dde_profile');
    localStorage.removeItem('dde_diagnostic_done');
    setUserId('');
    setUserName('');
    setDiagnosticDone(false);
    setProfile({ degree: 'BTech', year: '2nd', interest: 'python' });
  }

  return (
    <AppContext.Provider value={{
      userId,   setUserId,
      userName, setUserName,
      profile,  setProfile,
      serverStatus,
      diagnosticDone, markDiagnosticDone,
      resetAllLocalState,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used inside AppProvider');
  return ctx;
}
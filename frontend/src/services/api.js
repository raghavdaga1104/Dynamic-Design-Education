// services/api.js
// ─────────────────────────────────────────────────────────────
// Central API service. ALL fetch calls go through here.
// Never call fetch() directly from components.
// ─────────────────────────────────────────────────────────────

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ── Core fetch wrapper ────────────────────────────────────────
async function apiCall(method, endpoint, body = null) {
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) options.body = JSON.stringify(body);

  const response = await fetch(`${API_BASE}${endpoint}`, options);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    // Attach status so callers can check error.status === 409 etc.
    const err = new Error(error.detail?.message || error.detail || 'API error');
    err.status = response.status;
    err.detail = error.detail;
    throw err;
  }

  return response.json();
}

// ── Health ────────────────────────────────────────────────────
export const health = {
  check: () => apiCall('GET', '/health'),
};

// ── Curriculum ────────────────────────────────────────────────
export const curriculum = {
  getAll: () => apiCall('GET', '/curriculum'),
  getQuestions: (unitId, userId) => apiCall('GET', `/curriculum/${unitId}/questions${userId ? `?user_id=${userId}` : ''}`),
  checkAnswer: (unitId, questionId, answerIdx) =>
    apiCall('POST', `/curriculum/${unitId}/questions/${questionId}/check?answer_idx=${answerIdx}`),
  // Fetches notes for a unit from python_course_dataset.json via backend
  // Returns: { unit_id, count, notes: [{id, unit, topic, concept, code, input_output, explanation}] }
  getNotes: (unitId) => apiCall('GET', `/curriculum/${unitId}/notes`),
};

// ── Diagnostic ───────────────────────────────────────────────
export const diagnostic = {
  getTopics: () => apiCall('GET', '/diagnostic/topics'),
  start: (userId, topic) => apiCall('POST', '/diagnostic/start', { user_id: userId, topic }),
  submit: (userId, topic, answers) =>
    apiCall('POST', '/diagnostic/submit', { user_id: userId, topic, answers }),
  skip: (userId, topic) => apiCall('POST', '/diagnostic/skip', { user_id: userId, topic }),
};

// ── Recommend ────────────────────────────────────────────────
export const recommend = {
  getNext: (userId, degree, year, interest) =>
    apiCall('POST', '/recommend', { user_id: userId, degree, year, interest }),
};

// ── Quiz ─────────────────────────────────────────────────────
export const quiz = {
  submitIRT: (userId, unitId, answers) =>
    apiCall('POST', '/quiz/submit-irt', { user_id: userId, unit_id: unitId, answers }),
};

// ── Learner ──────────────────────────────────────────────────
export const learner = {
  getState: (userId) => apiCall('GET', `/learner/${userId}`),
  reset: (userId) => apiCall('POST', `/learner/${userId}/reset`),
  getSkillTree: (userId, topic = null) =>
    apiCall('GET', `/skill-tree/${userId}${topic ? `?topic=${topic}` : ''}`),
};

// ── Flashcards ───────────────────────────────────────────────
export const flashcard = {
  checkGate: (userId) => apiCall('GET', `/flashcard/gate/${userId}`),
  getSchedule: (userId) => apiCall('GET', `/flashcard/schedule/${userId}`),
  getDue: (userId) => apiCall('GET', `/flashcard/due/${userId}`),
  review: (userId, unitId, quality, currentDay = 0) =>
    apiCall('POST', '/flashcard/review', {
      user_id: userId,
      unit_id: unitId,
      quality,
      current_day: currentDay,
    }),
};

// ── Chat ─────────────────────────────────────────────────────
export const chat = {
  ask: (userId, question, unitContext, mode = 'question') =>
    apiCall('POST', '/chat', {
      user_id: userId,
      question,
      unit_id: unitContext.unit_id,
      unit_title: unitContext.display_name || unitContext.unit_title || '',
      unit_domain: unitContext.domain || unitContext.unit_domain || '',
      unit_notes: unitContext.currentNoteText || '',
      mode,
    }),
};

// ── Mistakes ─────────────────────────────────────────────────
export const mistakes = {
  getInsights: (userId) => apiCall('GET', `/mistakes/insights/${userId}`),
  getLog: (userId, limit = 50) =>
    apiCall('GET', `/mistakes/log/${userId}?limit=${limit}&wrong_only=true`),
  getConceptSummary: (userId) => apiCall('GET', `/mistakes/concept-summary/${userId}`),
};

// ── ATS ──────────────────────────────────────────────────────
export const ats = {
  analyze: (userId, resumeText, jobDescription) =>
    apiCall('POST', '/ats/analyze', {
      user_id: userId,
      resume_text: resumeText,
      job_description: jobDescription,
    }),
  improve: (userId, resumeText, jobDescription, targetRole = '') =>
    apiCall('POST', '/ats/improve', {
      user_id: userId,
      resume_text: resumeText,
      job_description: jobDescription,
      target_role: targetRole,
    }),
};
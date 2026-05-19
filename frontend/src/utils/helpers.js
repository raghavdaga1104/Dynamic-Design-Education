// utils/helpers.js
// ─────────────────────────────────────────────────────────────
// Pure utility functions used across multiple components.
// No API calls, no state — just data transformations.
// ─────────────────────────────────────────────────────────────

/**
 * Convert a mastery number (0-1) to a human-readable label.
 * Matches backend mastery_level labels exactly.
 */
export function masteryLabel(mastery) {
  if (mastery >= 0.80) return 'Mastered';
  if (mastery >= 0.60) return 'Proficient';
  if (mastery >= 0.30) return 'Developing';
  return 'Beginner';
}

/**
 * Get a CSS color class name for a mastery level.
 */
export function masteryColor(mastery) {
  if (mastery >= 0.80) return 'mastery-mastered';
  if (mastery >= 0.60) return 'mastery-proficient';
  if (mastery >= 0.30) return 'mastery-developing';
  return 'mastery-beginner';
}

/**
 * Convert a 0-1 mastery value to a percentage string.
 */
export function masteryPercent(mastery) {
  return `${Math.round(mastery * 100)}%`;
}

/**
 * Get color class for a unit status.
 */
export function statusColor(status) {
  if (status === 'completed') return 'status-completed';
  if (status === 'unlocked') return 'status-unlocked';
  return 'status-locked';
}

/**
 * Get emoji icon for a domain.
 */
export function domainIcon(domain) {
  const icons = {
    python: '🐍',
    'data structures': '🌲',
    oop: '🔷',
    algorithms: '⚙️',
  };
  return icons[domain?.toLowerCase()] || '📚';
}

/**
 * Get a short color tag for a domain.
 */
export function domainColor(domain) {
  const colors = {
    python: '#f59e0b',
    'data structures': '#10b981',
    oop: '#6366f1',
    algorithms: '#ef4444',
  };
  return colors[domain?.toLowerCase()] || '#64748b';
}

/**
 * Format a difficulty label with a color.
 */
export function difficultyColor(difficulty) {
  if (difficulty === 'easy') return '#10b981';
  if (difficulty === 'medium') return '#f59e0b';
  if (difficulty === 'hard') return '#ef4444';
  return '#64748b';
}

/**
 * Truncate a string to maxLength with ellipsis.
 */
export function truncate(str, maxLength = 80) {
  if (!str) return '';
  return str.length > maxLength ? str.slice(0, maxLength) + '...' : str;
}

/**
 * Generate a unique user ID (for new users without a saved ID).
 */
export function generateUserId() {
  return `user_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

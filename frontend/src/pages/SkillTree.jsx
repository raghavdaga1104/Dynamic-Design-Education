// pages/SkillTree.jsx
// ─────────────────────────────────────────────────────────────
// Visual skill tree showing all 14 units with status:
// completed / unlocked / locked.
// Filterable by domain. Shows mastery per unit.
// ─────────────────────────────────────────────────────────────

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { learner as learnerApi } from '../services/api';
import { Card, Spinner, Badge, Button, Alert } from '../components/ui';
import { domainIcon, domainColor, masteryPercent } from '../utils/helpers';

const DOMAINS = ['all', 'python', 'data structures', 'oop', 'algorithms'];

export default function SkillTree() {
  const { userId } = useApp();
  const navigate = useNavigate();

  const [tree, setTree]     = useState(null);
  const [domain, setDomain] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState('');

  useEffect(() => {
    loadTree();
  }, [userId, domain]);

  async function loadTree() {
    setLoading(true);
    try {
      const data = await learnerApi.getSkillTree(userId, domain === 'all' ? null : domain);
      setTree(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <div className="page"><Spinner message="Loading skill tree…" /></div>;
  if (error)   return <div className="page"><Alert type="error">{error}</Alert></div>;
  if (!tree)   return null;

  const nodes = tree.nodes || [];

  const statusIcon  = { completed: '✓', unlocked: '▶', locked: '⌀' };
  const statusLabel = { completed: 'Completed', unlocked: 'Unlocked', locked: 'Locked' };
  const statusClr   = { completed: '#10b981', unlocked: '#6366f1', locked: '#475569' };

  return (
    <div className="page skill-tree-page">
      {/* Header */}
      <div className="page-header">
        <h1 className="page-title">Skill Tree</h1>
        <div className="tree-summary">
          <Badge color="#10b981">✓ {tree.completed} Completed</Badge>
          <Badge color="#6366f1">▶ {tree.unlocked} Unlocked</Badge>
          <Badge color="#475569">⌀ {tree.locked} Locked</Badge>
        </div>
      </div>

      {/* Domain filter */}
      <div className="domain-filter">
        {DOMAINS.map(d => (
          <button
            key={d}
            className={`filter-btn ${domain === d ? 'filter-active' : ''}`}
            onClick={() => setDomain(d)}
            style={domain === d ? { borderColor: domainColor(d), color: domainColor(d) } : undefined}
          >
            {d !== 'all' && domainIcon(d)} {d}
          </button>
        ))}
      </div>

      {/* Tree nodes */}
      <div className="tree-grid">
        {nodes.map(node => (
          <div
            key={node.id}
            className={`tree-node node-${node.status} ${node.is_current ? 'node-current' : ''}`}
            style={{ '--domain-color': domainColor(node.domain) }}
          >
            {/* Status badge top-right */}
            <div className="node-status-badge" style={{ backgroundColor: statusClr[node.status] + '22', color: statusClr[node.status] }}>
              {statusIcon[node.status]} {statusLabel[node.status]}
            </div>

            {/* Domain icon */}
            <div className="node-icon">{domainIcon(node.domain)}</div>

            <h3 className="node-title">{node.title}</h3>
            <p className="node-desc">{node.description}</p>

            {/* Skills */}
            {node.skills_taught?.length > 0 && (
              <div className="node-skills">
                {node.skills_taught.map(s => (
                  <Badge key={s} color={domainColor(node.domain)}>{s}</Badge>
                ))}
              </div>
            )}

            {/* Mastery bar */}
            {node.mastery != null && node.mastery > 0.1 && (
              <div className="node-mastery">
                <div className="mastery-track">
                  <div
                    className="mastery-fill"
                    style={{
                      width: masteryPercent(node.mastery),
                      backgroundColor: node.mastery >= 0.8 ? '#10b981' : '#6366f1',
                    }}
                  />
                </div>
                <span className="mastery-pct">{masteryPercent(node.mastery)}</span>
              </div>
            )}

            {/* Prereqs */}
            {node.prereq_skills?.length > 0 && (
              <div className="node-prereqs">
                <span className="prereq-label">Requires: </span>
                {node.prereq_skills.map(s => (
                  <span key={s} className="prereq-tag">{s}</span>
                ))}
              </div>
            )}

            {/* Action */}
            {(node.status === 'unlocked' || node.status === 'completed') && (
              <Button
                size="sm"
                className="node-action-btn"
                onClick={() => navigate('/learn', {
                  state: {
                    forcedUnit: {
                      unit_id:      node.id,
                      display_name: node.title,
                      description:  node.description,
                      domain:       node.domain,
                      mcts_details: null,
                      quiz_question: null,
                    }
                  }
                })}
              >
                Study →
              </Button>
            )}
            {node.is_current && (
              <div className="node-current-label">← Current</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
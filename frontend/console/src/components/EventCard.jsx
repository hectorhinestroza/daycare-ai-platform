import { useState } from 'react';

const EVENT_ICONS = {
  food: '🍽️',
  nap: '😴',
  potty: '🚽',
  activity: '⚽',
  kudos: '⭐',
  incident: '⚠️',
  medication: '💊',
  observation: '👀',
  health_check: '🩺',
  absence: '📋',
  note: '📝',
};

const TIER_BADGE = {
  director: { label: 'Director Review', className: 'badge-director' },
  teacher: { label: 'Teacher Review', className: 'badge-teacher' },
};

export default function EventCard({ event, centerId, onAction }) {
  const [editing, setEditing] = useState(false);
  const [editFields, setEditFields] = useState({
    child_name: event.child_name,
    details: event.details || '',
  });
  const [loading, setLoading] = useState(false);

  const icon = EVENT_ICONS[event.event_type] || '📋';
  const tier = TIER_BADGE[event.review_tier] || TIER_BADGE.teacher;
  const confidence = Math.round(event.confidence_score * 100);
  const isLowConfidence = event.confidence_score < 0.7;
  const time = event.event_time
    ? new Date(event.event_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : null;
  const created = event.created_at
    ? new Date(event.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '';

  async function handleAction(action) {
    setLoading(true);
    try {
      await onAction(action, event.id, action === 'edit' ? editFields : null);
      if (action === 'edit') setEditing(false);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={`event-card ${isLowConfidence ? 'low-confidence' : ''} ${loading ? 'card-loading' : ''}`}>
      <div className="card-header">
        <span className="event-icon">{icon}</span>
        <span className="event-type">{event.event_type}</span>
        <span className={`badge ${tier.className}`}>{tier.label}</span>
        {isLowConfidence && <span className="badge badge-warning">⚠ Low Confidence</span>}
        <span className="confidence">{confidence}%</span>
      </div>

      <div className="card-body">
        {editing ? (
          <div className="edit-form">
            <label>
              Child Name
              <input
                type="text"
                value={editFields.child_name}
                onChange={(e) => setEditFields({ ...editFields, child_name: e.target.value })}
              />
            </label>
            <label>
              Details
              <textarea
                value={editFields.details}
                onChange={(e) => setEditFields({ ...editFields, details: e.target.value })}
                rows={2}
              />
            </label>
          </div>
        ) : (
          <>
            <h3 className="child-name">{event.child_name}</h3>
            <p className="event-details">{event.details || 'No details'}</p>
          </>
        )}
        <div className="card-meta">
          {time && <span className="event-time">🕐 {time}</span>}
          <span className="created-at">Received {created}</span>
        </div>
      </div>

      <div className="card-actions">
        {editing ? (
          <>
            <button className="btn btn-approve" onClick={() => handleAction('edit')} disabled={loading}>
              Save
            </button>
            <button className="btn btn-secondary" onClick={() => setEditing(false)} disabled={loading}>
              Cancel
            </button>
          </>
        ) : (
          <>
            <button className="btn btn-approve" onClick={() => handleAction('approve')} disabled={loading}>
              ✅ Approve
            </button>
            <button className="btn btn-edit" onClick={() => setEditing(true)} disabled={loading}>
              ✏️ Edit
            </button>
            <button className="btn btn-reject" onClick={() => handleAction('reject')} disabled={loading}>
              ❌ Reject
            </button>
          </>
        )}
      </div>
    </div>
  );
}

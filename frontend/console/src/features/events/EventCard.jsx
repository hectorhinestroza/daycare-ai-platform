import { useState } from 'react';

const EVENT_META = {
  food:         { icon: 'restaurant',       accentClass: 'bg-tertiary-container' },
  nap:          { icon: 'bedtime',           accentClass: 'bg-primary-container' },
  potty:        { icon: 'baby_changing_station', accentClass: 'bg-surface-container-high' },
  activity:     { icon: 'sports_soccer',    accentClass: 'bg-secondary' },
  kudos:        { icon: 'kid_star',          accentClass: 'bg-secondary-fixed' },
  incident:     { icon: 'warning',           accentClass: 'bg-[#facc15]' },
  medication:   { icon: 'medication',        accentClass: 'bg-primary-container' },
  observation:  { icon: 'visibility',        accentClass: 'bg-tertiary-fixed' },
  health_check: { icon: 'stethoscope',       accentClass: 'bg-surface-container-high' },
  absence:      { icon: 'event_busy',        accentClass: 'bg-surface-container-high' },
  note:         { icon: 'sticky_note_2',     accentClass: 'bg-tertiary-fixed' },
};

const DEFAULT_META = { icon: 'article', accentClass: 'bg-surface-container-high' };

export default function EventCard({ event, onAction, readOnly = false }) {
  const [editing, setEditing] = useState(false);
  const [editFields, setEditFields] = useState({
    child_name: event.child_name,
    details: event.details || '',
  });
  const [loading, setLoading] = useState(false);

  const meta = EVENT_META[event.event_type] || DEFAULT_META;
  const confidence = Math.round(event.confidence_score * 100);
  const isLowConfidence = event.confidence_score < 0.7;

  const time = event.event_time
    ? new Date(event.event_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : null;

  async function doAction(action) {
    setLoading(true);
    try {
      await onAction(action, event.id, action === 'edit' ? editFields : null);
      if (action === 'edit') setEditing(false);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className={`japandi-card p-6 rounded-lg shadow-ambient relative overflow-hidden card-appear ${
        loading ? 'opacity-60 pointer-events-none' : ''
      }`}
    >
      {/* 5% border for high-end definition without boxiness */}
      <div className="absolute inset-0 rounded-lg border border-outline-variant/5 pointer-events-none" />
      {/* Left accent strip */}
      <div className={`absolute top-0 left-0 w-1 h-full ${meta.accentClass}`} />

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        {/* Content */}
        <div className="flex-1">
          {/* Event type + timestamp */}
          <div className="flex items-center gap-3 mb-2">
            <span className="material-symbols-outlined text-on-surface-variant text-lg">{meta.icon}</span>
            <span className="font-label text-xs tracking-widest uppercase text-on-surface-variant/60">
              {event.event_type?.replace(/_/g, ' ')}
            </span>
            {time && (
              <>
                <span className="text-xs text-on-surface-variant/40">•</span>
                <span className="text-xs text-on-surface-variant/60">{time}</span>
              </>
            )}
            {isLowConfidence && (
              <span className="ml-auto text-[10px] px-2 py-0.5 bg-tertiary-fixed text-on-tertiary-fixed-variant rounded-full uppercase font-bold tracking-wider">
                {confidence}% Match
              </span>
            )}
          </div>

          {/* Body */}
          {editing ? (
            <div className="flex flex-col gap-3 mt-3">
              <div>
                <label className="text-xs font-medium text-on-surface-variant mb-1 block">Child Name</label>
                <input
                  type="text"
                  value={editFields.child_name}
                  onChange={(e) => setEditFields({ ...editFields, child_name: e.target.value })}
                  className="w-full bg-surface-container-highest rounded-DEFAULT px-4 py-2 text-sm text-on-surface outline-none focus:bg-surface-container-lowest border border-transparent focus:border-outline-variant/20 transition-colors"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-on-surface-variant mb-1 block">Details</label>
                <textarea
                  value={editFields.details}
                  onChange={(e) => setEditFields({ ...editFields, details: e.target.value })}
                  rows={2}
                  className="w-full bg-surface-container-highest rounded-DEFAULT px-4 py-2 text-sm text-on-surface outline-none focus:bg-surface-container-lowest border border-transparent focus:border-outline-variant/20 transition-colors resize-none"
                />
              </div>
            </div>
          ) : (
            <>
              <p className="text-lg text-on-surface leading-snug">
                {event.details || 'No details'}
              </p>
              {!isLowConfidence && (
                <div className="mt-3">
                  <span className="bg-secondary-fixed text-on-secondary-fixed-variant text-[10px] font-bold px-2 py-1 rounded-sm uppercase tracking-tighter">
                    Ready to Publish
                  </span>
                </div>
              )}
            </>
          )}
        </div>

        {/* Actions */}
        {readOnly ? (
          <div className="flex items-center gap-3 shrink-0">
            <span
              className={`text-xs font-bold px-3 py-1.5 rounded-full uppercase tracking-wide ${
                event.status === 'APPROVED'
                  ? 'bg-secondary-fixed text-on-secondary-fixed-variant'
                  : 'bg-error-container text-on-error-container'
              }`}
            >
              {event.status === 'APPROVED' ? 'Approved' : 'Rejected'}
            </span>
            {event.reviewed_at && (
              <span className="text-xs text-on-surface-variant">
                {new Date(event.reviewed_at).toLocaleString([], {
                  month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
                })}
              </span>
            )}
          </div>
        ) : editing ? (
          <div className="flex items-center gap-3 shrink-0">
            <button className="btn-secondary" onClick={() => setEditing(false)} disabled={loading}>
              Cancel
            </button>
            <button className="btn-primary" onClick={() => doAction('edit')} disabled={loading}>
              Save
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-3 shrink-0">
            <button className="btn-secondary" onClick={() => setEditing(true)} disabled={loading}>
              Edit
            </button>
            <button
              className="btn-secondary !text-on-error-container !bg-error-container/60 hover:!bg-error-container"
              onClick={() => doAction('reject')}
              disabled={loading}
            >
              Reject
            </button>
            <button className="btn-primary" onClick={() => doAction('approve')} disabled={loading}>
              Confirm
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

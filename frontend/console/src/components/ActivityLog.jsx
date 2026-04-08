import { useState, useEffect } from 'react';
import { fetchActivityLog } from '../api';
import EmptyState from './EmptyState';

const ACTION_META = {
  APPROVE:       { icon: 'check_circle', chipClass: 'bg-secondary-fixed text-on-secondary-fixed-variant',  label: 'Approved' },
  BATCH_APPROVE: { icon: 'done_all',     chipClass: 'bg-secondary-fixed text-on-secondary-fixed-variant',  label: 'Batch Approved' },
  REJECT:        { icon: 'cancel',       chipClass: 'bg-error-container text-on-error-container',           label: 'Rejected' },
  EDIT:          { icon: 'edit',         chipClass: 'bg-tertiary-fixed text-on-tertiary-fixed-variant',     label: 'Edited' },
  CREATE:        { icon: 'add_circle',   chipClass: 'bg-primary-fixed text-on-primary-container',           label: 'Created' },
};

const DEFAULT_META = { icon: 'info', chipClass: 'bg-surface-container-high text-on-surface-variant', label: 'Action' };

function getActivityMessage(log) {
  const { action, details } = log;
  const child = details?.child_name || 'an unknown child';
  const evt = details?.event_type || 'event';

  switch (action) {
    case 'APPROVE':
      return <span>Approved <strong className="text-on-surface">{evt}</strong> for <strong className="text-on-surface">{child}</strong>.</span>;
    case 'REJECT':
      return <span>Rejected <strong className="text-on-surface">{evt}</strong> for <strong className="text-on-surface">{child}</strong>.</span>;
    case 'BATCH_APPROVE':
      return <span>Batch approved <strong className="text-on-surface">{details?.count || 'multiple'}</strong> events for <strong className="text-on-surface">{child}</strong>.</span>;
    case 'EDIT':
      return <span>Edited <strong className="text-on-surface">{evt}</strong> for <strong className="text-on-surface">{child}</strong>.</span>;
    default:
      return <span>Performed {action} on {child}.</span>;
  }
}

export default function ActivityLog({ centerId }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!centerId) return;
    setLoading(true);
    fetchActivityLog(centerId)
      .then((data) => { setLogs(data); setError(null); })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [centerId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4 text-on-surface-variant">
        <div className="spinner" />
        <p className="text-sm font-medium">Loading activity…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-error-container text-on-error-container px-4 py-3 rounded-lg text-sm">
        {error}
      </div>
    );
  }

  if (logs.length === 0) {
    return <div className="mt-8"><EmptyState role="history" /></div>;
  }

  const grouped = logs.reduce((acc, log) => {
    const name = log.teacher_name || 'System';
    if (!acc[name]) acc[name] = [];
    acc[name].push(log);
    return acc;
  }, {});

  return (
    <>
      {/* Hero */}
      <section className="mb-10">
        <h2 className="font-headline text-4xl md:text-5xl text-on-surface mb-2 tracking-tight">Activity Log</h2>
        <p className="text-on-surface-variant max-w-md leading-relaxed">
          A full audit trail of all review actions taken by teachers and directors.
        </p>
      </section>

      <div className="space-y-10">
        {Object.entries(grouped).map(([teacherName, teacherLogs]) => (
          <section key={teacherName} className="space-y-4">
            {/* Teacher group header */}
            <div className="flex items-center gap-4 px-2">
              <div className="w-11 h-11 rounded-full bg-surface-container-highest flex items-center justify-center text-primary font-semibold text-base border border-outline-variant/15 shrink-0">
                {teacherName.charAt(0).toUpperCase()}
              </div>
              <h3 className="font-headline text-2xl text-on-surface">{teacherName}</h3>
              <span className="ml-1 text-xs font-medium text-on-surface-variant bg-surface-container px-2.5 py-1 rounded-full">
                {teacherLogs.length}
              </span>
            </div>

            {/* Log entries */}
            <div className="space-y-4">
              {teacherLogs.map((log) => {
                const meta = ACTION_META[log.action] || DEFAULT_META;
                return (
                  <div
                    key={log.id}
                    className="japandi-card p-5 rounded-lg shadow-ambient border border-outline-variant/10 card-appear"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${meta.chipClass}`}>
                        <span className="material-symbols-outlined text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>
                          {meta.icon}
                        </span>
                        {meta.label}
                      </span>
                      <span className="text-xs text-on-surface-variant">
                        {new Date(log.created_at).toLocaleString([], {
                          month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
                        })}
                      </span>
                    </div>

                    <p className="text-sm text-on-surface-variant">{getActivityMessage(log)}</p>

                    {/* Edit diff */}
                    {log.action === 'EDIT' && log.details?.changes && (
                      <div className="mt-3 bg-surface-container-low rounded-md p-3 space-y-2">
                        {Object.entries(log.details.changes).map(([field, change]) => (
                          <div key={field} className="text-xs">
                            <span className="text-on-surface-variant capitalize">{field.replace('_', ' ')}: </span>
                            <span className="line-through text-error/70 mr-2">{String(change.old)}</span>
                            <span className="text-secondary font-medium">{String(change.new)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </>
  );
}

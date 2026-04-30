import { useState, useEffect, useCallback } from 'react';
import EventCard from '../../features/events/EventCard';
import EmptyState from '../../components/ui/EmptyState';
import { fetchDirectorQueue, approveEvent, rejectEvent, editEvent, batchApprove } from '../../api';

export default function DirectorDashboard({ centerId, addToast }) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadEvents = useCallback(async () => {
    if (!centerId) {
      setError('No center_id provided.');
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDirectorQueue(centerId);
      setEvents(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [centerId]);

  useEffect(() => {
    loadEvents();
    const interval = setInterval(loadEvents, 15000);
    return () => clearInterval(interval);
  }, [loadEvents]);

  async function handleAction(action, eventId, editData) {
    try {
      if (action === 'approve') {
        await approveEvent(centerId, eventId);
        addToast('Event approved');
      } else if (action === 'reject') {
        await rejectEvent(centerId, eventId);
        addToast('Event rejected', 'info');
      } else if (action === 'edit') {
        await editEvent(centerId, eventId, editData);
        addToast('Event updated');
      }
      setEvents((prev) => prev.filter((e) => e.id !== eventId));
    } catch (err) {
      addToast(err.message, 'error');
    }
  }

  async function handleBatchApprove({ childName, batchId }) {
    try {
      const result = await batchApprove(centerId, { childName, batchId });
      addToast(result.message);
      if (batchId) {
        setEvents((prev) => prev.filter((e) => e.batch_id !== batchId));
      } else {
        setEvents((prev) => prev.filter((e) => e.child_name !== childName));
      }
    } catch (err) {
      addToast(err.message, 'error');
    }
  }

  // Separate fan-out batch events from regular single-child events.
  // Batch events share a batch_id; regular events do not.
  const batchGroups = {}; // batch_id → [events]
  const regularGroups = {}; // child_name → [events]
  for (const event of events) {
    if (event.batch_id) {
      if (!batchGroups[event.batch_id]) batchGroups[event.batch_id] = [];
      batchGroups[event.batch_id].push(event);
    } else {
      const name = event.child_name || 'Unknown';
      if (!regularGroups[name]) regularGroups[name] = [];
      regularGroups[name].push(event);
    }
  }

  if (error) {
    return (
      <div className="mb-6 flex items-center justify-between bg-error-container text-on-error-container px-4 py-3 rounded-lg">
        <span className="text-sm">{error}</span>
        <button onClick={() => setError(null)} className="ml-3 hover:opacity-70">
          <span className="material-symbols-outlined text-base">close</span>
        </button>
      </div>
    );
  }

  if (loading && events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4 text-on-surface-variant">
        <div className="spinner" />
        <p className="text-sm font-medium">Loading Queue…</p>
      </div>
    );
  }

  return (
    <>
      <section className="mb-10">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h2 className="font-headline text-4xl md:text-5xl text-on-surface mb-2 tracking-tight">
              Needs Attention
            </h2>
            <p className="text-on-surface-variant max-w-md leading-relaxed">
              {events.length} flagged event{events.length !== 1 ? 's' : ''} need your attention today.
            </p>
          </div>
          {events.length > 0 && (
            <div className="flex gap-2 shrink-0">
              <span className="ai-chip">
                <span className="material-symbols-outlined text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>
                  auto_awesome
                </span>
                {events.length} Flags
              </span>
            </div>
          )}
        </div>
      </section>

      {events.length === 0 ? (
        <EmptyState role="director" />
      ) : (
        <div className="space-y-10">
          {/* ── Fan-out batch groups ── */}
          {Object.entries(batchGroups).map(([batchId, batchEvents]) => {
            const sample = batchEvents[0];
            const childNames = batchEvents.map((e) => e.child_name);
            return (
              <section key={batchId} className="space-y-4">
                <div className="glass-panel rounded-xl p-5 border border-outline-variant/20">
                  {/* Header */}
                  <div className="flex items-start gap-3 mb-4">
                    <div className="w-10 h-10 rounded-full bg-primary-fixed flex items-center justify-center shrink-0">
                      <span className="material-symbols-outlined text-on-primary-container text-lg" style={{ fontVariationSettings: "'FILL' 1" }}>
                        groups
                      </span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-semibold uppercase tracking-wider text-primary">{sample.event_type}</span>
                        <span className="text-xs text-on-surface-variant bg-surface-container px-2 py-0.5 rounded-full">
                          All {batchEvents.length} children
                        </span>
                      </div>
                      <p className="text-sm font-medium text-on-surface mt-0.5">{sample.details}</p>
                    </div>
                    <button
                      onClick={() => handleBatchApprove({ batchId })}
                      className="ai-chip text-xs shrink-0"
                    >
                      <span className="material-symbols-outlined text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>done_all</span>
                      Approve All {batchEvents.length}
                    </button>
                  </div>
                  {/* Child list */}
                  <div className="flex flex-wrap gap-2">
                    {childNames.map((name) => (
                      <span key={name} className="text-xs bg-surface-container text-on-surface-variant px-2.5 py-1 rounded-full">
                        {name}
                      </span>
                    ))}
                  </div>
                </div>
              </section>
            );
          })}

          {/* ── Regular per-child groups ── */}
          {Object.entries(regularGroups).map(([childName, childEvents]) => (
            <section key={childName} className="space-y-4">
              <div className="flex items-center gap-4 px-2">
                <div className="w-11 h-11 rounded-full bg-surface-container-highest flex items-center justify-center text-primary font-semibold text-base border border-outline-variant/15 shrink-0">
                  {childName.charAt(0).toUpperCase()}
                </div>
                <h3 className="font-headline text-2xl text-on-surface">{childName}</h3>
                <span className="ml-1 text-xs font-medium text-on-surface-variant bg-surface-container px-2.5 py-1 rounded-full">
                  {childEvents.length}
                </span>
                {childEvents.length > 1 && (
                  <button onClick={() => handleBatchApprove({ childName })} className="ml-auto ai-chip text-xs">
                    <span className="material-symbols-outlined text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>
                      done_all
                    </span>
                    Approve All
                  </button>
                )}
              </div>
              <div className="space-y-4">
                {childEvents.map((event) => (
                  <EventCard
                    key={event.id}
                    event={event}
                    centerId={centerId}
                    onAction={handleAction}
                    readOnly={false}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </>
  );
}

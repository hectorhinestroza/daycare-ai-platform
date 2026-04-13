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

  async function handleBatchApprove(childName) {
    try {
      const result = await batchApprove(centerId, childName);
      addToast(result.message);
      setEvents((prev) => prev.filter((e) => e.child_name !== childName));
    } catch (err) {
      addToast(err.message, 'error');
    }
  }

  const grouped = events.reduce((acc, event) => {
    const name = event.child_name || 'Unknown';
    if (!acc[name]) acc[name] = [];
    acc[name].push(event);
    return acc;
  }, {});

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
          {Object.entries(grouped).map(([childName, childEvents]) => (
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
                  <button onClick={() => handleBatchApprove(childName)} className="ml-auto ai-chip text-xs">
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

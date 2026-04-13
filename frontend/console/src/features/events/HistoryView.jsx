import { useState, useEffect, useCallback } from 'react';
import EventCard from './EventCard';
import EmptyState from '../../components/ui/EmptyState';
import { fetchHistory } from '../../api';

export default function HistoryView({ centerId, addToast }) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadEvents = useCallback(async () => {
    if (!centerId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchHistory(centerId);
      setEvents(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [centerId]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

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
      </div>
    );
  }

  if (loading && events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4 text-on-surface-variant">
        <div className="spinner" />
        <p className="text-sm font-medium">Loading history…</p>
      </div>
    );
  }

  return (
    <>
      <section className="mb-10">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h2 className="font-headline text-4xl md:text-5xl text-on-surface mb-2 tracking-tight">
              Review History
            </h2>
            <p className="text-on-surface-variant max-w-md leading-relaxed">
              Browse previously reviewed events and their outcomes.
            </p>
          </div>
        </div>
      </section>

      {events.length === 0 ? (
        <EmptyState role="history" />
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
              </div>
              <div className="space-y-4">
                {childEvents.map((event) => (
                  <EventCard
                    key={event.id}
                    event={event}
                    centerId={centerId}
                    readOnly={true}
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

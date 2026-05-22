import { useState, useEffect, useCallback } from 'react';
import EventCard from './EventCard';
import EmptyState from '../../components/ui/EmptyState';
import { fetchHistory } from '../../api';

export default function DirectorHistoryView({ centerId }) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [groupBy, setGroupBy] = useState('child'); // 'child' | 'teacher'

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
    const key = groupBy === 'child'
      ? (event.child_name || 'Unknown')
      : (event.teacher_name || 'System');
    if (!acc[key]) acc[key] = [];
    acc[key].push(event);
    return acc;
  }, {});

  if (error) {
    return (
      <div className="mb-6 bg-error-container text-on-error-container px-4 py-3 rounded-lg text-sm">
        {error}
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
              History
            </h2>
            <p className="text-on-surface-variant max-w-md leading-relaxed">
              {events.length} reviewed event{events.length !== 1 ? 's' : ''} across all teachers and children.
            </p>
          </div>

          {/* Group-by toggle */}
          <div className="flex items-center gap-1 bg-surface-container rounded-full p-1 shrink-0">
            <button
              onClick={() => setGroupBy('child')}
              className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all duration-200 ${
                groupBy === 'child'
                  ? 'bg-primary text-on-primary shadow-sm'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              By Child
            </button>
            <button
              onClick={() => setGroupBy('teacher')}
              className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all duration-200 ${
                groupBy === 'teacher'
                  ? 'bg-primary text-on-primary shadow-sm'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              By Teacher
            </button>
          </div>
        </div>
      </section>

      {events.length === 0 ? (
        <EmptyState role="history" />
      ) : (
        <div className="space-y-10">
          {Object.entries(grouped).map(([groupKey, groupEvents]) => (
            <section key={groupKey} className="space-y-4">
              {/* Group header */}
              <div className="flex items-center gap-4 px-2">
                <div className="w-11 h-11 rounded-full bg-surface-container-highest flex items-center justify-center text-primary font-semibold text-base border border-outline-variant/15 shrink-0">
                  {groupKey.charAt(0).toUpperCase()}
                </div>
                <h3 className="font-headline text-2xl text-on-surface">{groupKey}</h3>
                <span className="ml-1 text-xs font-medium text-on-surface-variant bg-surface-container px-2.5 py-1 rounded-full">
                  {groupEvents.length}
                </span>
              </div>

              {/* Event cards with attribution row */}
              <div className="space-y-4">
                {groupEvents.map((event) => (
                  <div key={event.id}>
                    <EventCard event={event} readOnly />
                    <div className="flex items-center gap-2 px-3 pt-2 pb-1 flex-wrap">
                      {groupBy === 'child' && event.teacher_name && (
                        <span className="text-xs text-on-surface-variant">
                          Logged by{' '}
                          <span className="font-medium text-on-surface">{event.teacher_name}</span>
                        </span>
                      )}
                      {groupBy === 'teacher' && (
                        <span className="text-xs text-on-surface-variant">
                          For{' '}
                          <span className="font-medium text-on-surface">{event.child_name}</span>
                        </span>
                      )}
                      <span className="text-xs text-on-surface-variant/60 bg-surface-container px-2 py-0.5 rounded-full capitalize">
                        {event.review_tier}
                      </span>
                      <span className="text-xs text-on-surface-variant/60 bg-surface-container px-2 py-0.5 rounded-full">
                        {Math.round(event.confidence_score * 100)}% confidence
      	            </span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </>
  );
}

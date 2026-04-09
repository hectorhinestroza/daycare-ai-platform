import { useState, useEffect, useCallback } from 'react';
import { fetchParentFeed, fetchChildPublic } from '../api';

const EVENT_ICON = {
  food: 'restaurant',
  nap: 'bedtime',
  potty: 'wc',
  activity: 'palette',
  incident: 'warning',
  medication: 'medication',
  mood: 'sentiment_satisfied',
  milestone: 'emoji_events',
  pickup: 'directions_car',
  dropoff: 'login',
  note: 'sticky_note_2',
};

const EVENT_COLOR = {
  food: 'bg-[#e8f5e9] text-[#2e7d32]',
  nap: 'bg-[#e3f2fd] text-[#1565c0]',
  potty: 'bg-[#fff3e0] text-[#e65100]',
  activity: 'bg-primary-fixed text-on-primary-container',
  incident: 'bg-error-container text-on-error-container',
  medication: 'bg-[#fce4ec] text-[#c62828]',
  mood: 'bg-tertiary-fixed text-on-tertiary-fixed-variant',
  milestone: 'bg-secondary-fixed text-on-secondary-fixed-variant',
  pickup: 'bg-surface-container-high text-on-surface-variant',
  dropoff: 'bg-surface-container-high text-on-surface-variant',
  note: 'bg-surface-container-high text-on-surface-variant',
};

function formatTime(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (d.toDateString() === today.toDateString()) return 'Today';
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return d.toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' });
}

function groupByDate(events) {
  const groups = {};
  for (const event of events) {
    const dateKey = new Date(event.event_time || event.created_at).toDateString();
    if (!groups[dateKey]) groups[dateKey] = [];
    groups[dateKey].push(event);
  }
  return Object.entries(groups).map(([dateKey, events]) => ({
    date: dateKey,
    label: formatDate(events[0].event_time || events[0].created_at),
    events,
  }));
}

export default function ParentPortal({ centerId, childId }) {
  const [child, setChild] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = useCallback(async () => {
    try {
      const [childData, feedData] = await Promise.all([
        fetchChildPublic(centerId, childId),
        fetchParentFeed(centerId, childId),
      ]);
      setChild(childData);
      setEvents(feedData);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [centerId, childId]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [loadData]);

  const dayGroups = groupByDate(events);

  return (
    <div className="min-h-screen bg-surface">
      {/* Header */}
      <header className="bg-surface/80 backdrop-blur-xl fixed top-0 w-full z-50 px-6 py-4">
        <div className="max-w-2xl mx-auto flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-primary-fixed flex items-center justify-center text-on-primary-container font-semibold text-sm">
            {child?.name?.charAt(0)?.toUpperCase() || '?'}
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="font-headline text-xl font-semibold text-on-surface truncate">
              {child?.name || 'Loading...'}
            </h1>
            <p className="text-xs text-on-surface-variant">Live Updates</p>
          </div>
          <button
            onClick={loadData}
            className="text-primary hover:opacity-70 transition-opacity"
            title="Refresh"
          >
            <span className="material-symbols-outlined">sync_alt</span>
          </button>
        </div>
      </header>

      {/* Content */}
      <main className="pt-24 pb-12 px-6 max-w-2xl mx-auto">
        {error && (
          <div className="mb-6 flex items-center justify-between bg-error-container text-on-error-container px-4 py-3 rounded-lg">
            <span className="text-sm">{error}</span>
            <button onClick={() => setError(null)} className="ml-3 hover:opacity-70">
              <span className="material-symbols-outlined text-base">close</span>
            </button>
          </div>
        )}

        {loading ? (
          <div className="flex flex-col items-center justify-center py-24 gap-4 text-on-surface-variant">
            <div className="spinner" />
            <p className="text-sm font-medium">Loading updates...</p>
          </div>
        ) : events.length === 0 ? (
          <div className="text-center py-24 text-on-surface-variant">
            <span className="material-symbols-outlined text-5xl text-outline mb-4 block">
              nest_cam_wired_stand
            </span>
            <h2 className="font-headline text-2xl text-on-surface mb-2">No updates yet</h2>
            <p className="text-sm max-w-xs mx-auto">
              Updates will appear here as your child's teacher records activities throughout the day.
            </p>
          </div>
        ) : (
          <div className="space-y-8">
            {dayGroups.map((group) => (
              <section key={group.date}>
                {/* Date header */}
                <div className="flex items-center gap-3 mb-4">
                  <h2 className="font-headline text-lg text-on-surface">{group.label}</h2>
                  <span className="text-xs text-on-surface-variant bg-surface-container px-2.5 py-0.5 rounded-full">
                    {group.events.length} {group.events.length === 1 ? 'update' : 'updates'}
                  </span>
                </div>

                {/* Timeline */}
                <div className="space-y-3">
                  {group.events.map((event) => (
                    <ParentEventCard key={event.id} event={event} />
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

function ParentEventCard({ event }) {
  const icon = EVENT_ICON[event.event_type] || 'circle';
  const colorClass = EVENT_COLOR[event.event_type] || EVENT_COLOR.note;
  const time = formatTime(event.event_time || event.created_at);

  return (
    <div className="japandi-card rounded-lg shadow-ambient p-4 flex gap-4 items-start card-appear">
      {/* Icon */}
      <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${colorClass}`}>
        <span className="material-symbols-outlined text-lg" style={{ fontVariationSettings: "'FILL' 1" }}>
          {icon}
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-medium uppercase tracking-wider text-on-surface-variant">
            {event.event_type}
          </span>
          {time && (
            <>
              <span className="text-on-surface-variant/30">·</span>
              <span className="text-xs text-on-surface-variant">{time}</span>
            </>
          )}
        </div>
        {event.details && (
          <p className="text-sm text-on-surface leading-relaxed">{event.details}</p>
        )}
      </div>
    </div>
  );
}

import { useState, useEffect, useCallback, useRef } from 'react';
import { fetchParentFeed, fetchChildPublic, fetchNarrative, generateNarrative } from '../../api/index';
import { fromApi } from '../../utils/time';

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

const TONE_CONFIG = {
  upbeat: { icon: 'sentiment_very_satisfied', label: 'Great day!', class: 'bg-[#e8f5e9] text-[#2e7d32]' },
  neutral: { icon: 'sentiment_neutral', label: 'Good day', class: 'bg-surface-container text-on-surface-variant' },
  'needs-attention': { icon: 'info', label: 'Needs attention', class: 'bg-error-container text-on-error-container' },
};

function todayDateString() {
  return new Date().toISOString().slice(0, 10); // YYYY-MM-DD
}

function formatTime(dateStr) {
  const d = fromApi(dateStr);
  if (!d) return '';
  return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function formatDate(dateStr) {
  const d = fromApi(dateStr);
  if (!d) return '';
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
    const d = fromApi(event.event_time || event.created_at);
    const dateKey = d.toDateString();
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
  const [narrative, setNarrative] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Guard: auto-trigger fires only once per session; manual retries always allowed
  const autoTriggered = useRef(false);

  const handleGenerate = useCallback(async () => {
    const today = todayDateString();
    setGenerating(true);
    try {
      const generated = await generateNarrative(centerId, childId, today);
      setNarrative(generated);
    } catch (err) {
      // Silent fail — parent sees the rule-based Daily Snapshot as fallback
      console.warn('Narrative generation failed:', err.message);
    } finally {
      setGenerating(false);
    }
  }, [centerId, childId]);

  const loadData = useCallback(async () => {
    try {
      const today = todayDateString();
      const [childData, feedData, narrativeData] = await Promise.all([
        fetchChildPublic(centerId, childId),
        fetchParentFeed(centerId, childId),
        fetchNarrative(centerId, childId, today),
      ]);
      setChild(childData);
      setEvents(feedData);
      setNarrative(narrativeData);
      setError(null);

      // Auto-trigger once per session when events exist but no narrative yet
      if (!narrativeData && !autoTriggered.current && feedData.length > 0) {
        autoTriggered.current = true;
        handleGenerate();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [centerId, childId, handleGenerate]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [loadData]);

  if (child?.status === 'PENDING_CONSENT') {
    return (
      <div className="min-h-screen bg-surface px-6 pt-32 text-center card-appear">
        <div className="w-20 h-20 bg-[#fff3e0] rounded-full flex items-center justify-center mx-auto mb-6 shadow-ambient">
          <span className="material-symbols-outlined text-4xl text-[#e65100]" style={{ fontVariationSettings: "'FILL' 1" }}>
            mark_email_unread
          </span>
        </div>
        <h2 className="font-headline text-3xl font-semibold mb-3 text-on-surface tracking-tight">Setup Required</h2>
        <p className="text-on-surface-variant text-base max-w-sm mx-auto leading-relaxed mb-6">
          Your portal for <span className="font-medium text-on-surface">{child.name.split(' ')[0]}</span> is almost ready! We sent a secure setup link to the primary email on file.
        </p>
        <p className="text-sm text-on-surface-variant">
          Please check your inbox (and spam folder) to complete your privacy setup and unlock the portal.
        </p>
      </div>
    );
  }

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
          <EmptyDay childName={child?.name} narrative={narrative} />
        ) : (
          <div className="space-y-8">
            {dayGroups.map((group, idx) => (
              <section key={group.date}>
                {/* Date header */}
                <div className="flex items-center gap-3 mb-4">
                  <h2 className="font-headline text-lg text-on-surface">{group.label}</h2>
                  <span className="text-xs text-on-surface-variant bg-surface-container px-2.5 py-0.5 rounded-full">
                    {group.events.length} {group.events.length === 1 ? 'update' : 'updates'}
                  </span>
                </div>

                {/* Today's summary — AI narrative takes priority over rule-based */}
                {idx === 0 && generating ? (
                  <NarrativeGenerating />
                ) : idx === 0 && narrative ? (
                  <EODNarrativeCard narrative={narrative} />
                ) : idx === 0 && group.events.length >= 2 ? (
                  <DailySummary events={group.events} childName={child?.name} />
                ) : null}

                {/* Photo gallery for today if photos exist */}
                {idx === 0 && <PhotoGallery events={group.events} narrative={narrative} />}

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

// ─── Empty state ──────────────────────────────────────────────

function EmptyDay({ childName, narrative }) {
  const firstName = childName?.split(' ')[0] || 'Your child';

  // If a narrative was generated despite no live-feed events (e.g. absence),
  // show it instead of the generic empty state.
  if (narrative) {
    return (
      <div className="py-12">
        <EODNarrativeCard narrative={narrative} />
      </div>
    );
  }

  return (
    <div className="text-center py-24 text-on-surface-variant">
      <span className="material-symbols-outlined text-5xl text-outline mb-4 block">
        nest_cam_wired_stand
      </span>
      <h2 className="font-headline text-2xl text-on-surface mb-2">No updates yet</h2>
      <p className="text-sm max-w-xs mx-auto">
        Updates for {firstName} will appear here as the teacher records activities throughout the day.
      </p>
    </div>
  );
}

// ─── Narrative generating skeleton ───────────────────────────

function NarrativeGenerating() {
  return (
    <div className="glass-panel rounded-xl p-5 mb-5 border border-outline-variant/20 animate-pulse">
      <div className="flex items-center gap-2 mb-3">
        <span className="material-symbols-outlined text-primary text-sm animate-spin">
          progress_activity
        </span>
        <span className="text-xs text-on-surface-variant">Composing today's summary…</span>
      </div>
      <div className="h-4 bg-surface-container rounded w-3/4 mb-2" />
      <div className="h-3 bg-surface-container rounded w-full mb-1.5" />
      <div className="h-3 bg-surface-container rounded w-5/6" />
    </div>
  );
}

// ─── EOD Narrative card (AI-generated) ───────────────────────

function EODNarrativeCard({ narrative }) {
  const tone = TONE_CONFIG[narrative.tone] || TONE_CONFIG.neutral;

  return (
    <div className="glass-panel rounded-xl p-5 mb-5 border border-outline-variant/20">
      {/* Tone chip + label */}
      <div className="flex items-center gap-2 mb-3">
        <span
          className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${tone.class}`}
        >
          <span className="material-symbols-outlined text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>
            {tone.icon}
          </span>
          {tone.label}
        </span>
        <span className="text-xs text-on-surface-variant ml-auto">End-of-Day Summary</span>
      </div>

      {/* Headline */}
      <h3 className="font-headline text-lg font-semibold text-on-surface mb-2 leading-snug">
        {narrative.headline}
      </h3>

      {/* Body */}
      <p className="text-sm text-on-surface-variant leading-relaxed">
        {narrative.body}
      </p>
    </div>
  );
}

// ─── Photo gallery ─────────────────────────────────────────

function PhotoGallery({ events, narrative }) {
  const photoCaptions = narrative?.photo_captions || {};

  // Collect photos with captions from narrative, or any event photos
  const photos = [];
  for (const event of events) {
    if (!event.photos) continue;
    for (const photo of event.photos) {
      if (photo.s3_url || photo.s3_key) {
        photos.push({
          id: photo.id,
          url: photo.s3_url,
          caption: photoCaptions[photo.id] || photo.caption || null,
        });
      }
    }
  }

  if (photos.length === 0) return null;

  return (
    <div className="mb-5">
      <p className="text-xs font-medium text-on-surface-variant uppercase tracking-wider mb-2">Photos</p>
      <div className="flex gap-3 overflow-x-auto pb-2 -mx-1 px-1">
        {photos.map((photo) => (
          <div key={photo.id} className="shrink-0 w-40">
            <div className="w-40 h-40 rounded-lg overflow-hidden bg-surface-container">
              <img src={photo.url} alt={photo.caption || 'Photo'} className="w-full h-full object-cover" />
            </div>
            {photo.caption && (
              <p className="text-xs text-on-surface-variant mt-1.5 leading-snug line-clamp-2">
                {photo.caption}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Event card ───────────────────────────────────────────────

function ParentEventCard({ event }) {
  const icon = EVENT_ICON[event.event_type] || 'circle';
  const colorClass = EVENT_COLOR[event.event_type] || EVENT_COLOR.note;
  const time = formatTime(event.event_time || event.created_at);

  return (
    <div className="japandi-card rounded-lg shadow-ambient p-4 flex gap-4 items-start card-appear">
      <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${colorClass}`}>
        <span className="material-symbols-outlined text-lg" style={{ fontVariationSettings: "'FILL' 1" }}>
          {icon}
        </span>
      </div>
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

// ─── Rule-based fallback (shown when no AI narrative yet) ─────

function DailySummary({ events, childName }) {
  const typeCounts = {};
  for (const e of events) {
    typeCounts[e.event_type] = (typeCounts[e.event_type] || 0) + 1;
  }

  const summaryParts = [];
  const tracked = ['food', 'nap', 'activity', 'potty'];
  const labels = { food: 'meal', nap: 'nap', activity: 'activity', potty: 'potty break' };
  let trackedTotal = 0;
  for (const key of tracked) {
    const count = typeCounts[key];
    if (count) {
      trackedTotal += count;
      const label = labels[key];
      summaryParts.push(`${count} ${count > 1 ? (key === 'activity' ? 'activities' : label + 's') : label}`);
    }
  }
  const otherCount = events.length - trackedTotal;
  if (otherCount > 0) summaryParts.push(`${otherCount} other update${otherCount > 1 ? 's' : ''}`);

  const firstName = childName?.split(' ')[0] || 'Your child';

  return (
    <div className="glass-panel rounded-lg p-4 mb-4">
      <div className="flex items-start gap-3">
        <span className="material-symbols-outlined text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>
          auto_awesome
        </span>
        <div>
          <p className="text-sm font-medium text-on-surface mb-1">Daily Snapshot</p>
          <p className="text-sm text-on-surface-variant leading-relaxed">
            {firstName} has had {summaryParts.join(', ')} so far today.
          </p>
        </div>
      </div>
    </div>
  );
}

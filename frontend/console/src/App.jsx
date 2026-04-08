import { useState, useEffect, useCallback } from 'react';
import EventCard from './components/EventCard';
import EmptyState from './components/EmptyState';
import Toast from './components/Toast';
import ActivityLog from './components/ActivityLog';
import {
  fetchTeacherQueue,
  fetchDirectorQueue,
  fetchHistory,
  approveEvent,
  rejectEvent,
  editEvent,
  batchApprove,
} from './api';

// Bottom nav config per role
const TEACHER_NAV = [
  { key: 'pending',  icon: 'auto_awesome', label: 'Today' },
  { key: 'history',  icon: 'history',      label: 'History' },
];

const DIRECTOR_NAV = [
  { key: 'pending',  icon: 'auto_awesome', label: 'Queue' },
  { key: 'history',  icon: 'history',      label: 'History' },
  { key: 'activity', icon: 'bar_chart',    label: 'Activity' },
];

function App() {
  const [role, setRole] = useState('teacher');
  const [view, setView] = useState('pending');

  // Enforce role-based view access
  useEffect(() => {
    if (role === 'teacher' && view === 'activity') {
      setView('pending');
    }
  }, [role, view]);

  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [toasts, setToasts] = useState([]);

  const params = new URLSearchParams(window.location.search);
  const centerId = params.get('center') || '';

  // ─── Toast helpers ─────────────────────────────────────────
  function addToast(message, type = 'success') {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
  }

  function removeToast(id) {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }

  // ─── Data loading ──────────────────────────────────────────
  const loadEvents = useCallback(async () => {
    if (!centerId) {
      setError('No center_id provided. Add ?center=YOUR_CENTER_ID to the URL.');
      setLoading(false);
      return;
    }
    if (view === 'activity') return;

    setLoading(true);
    setError(null);
    try {
      let data;
      if (view === 'history') {
        data = await fetchHistory(centerId);
      } else if (role === 'director') {
        data = await fetchDirectorQueue(centerId);
      } else {
        data = await fetchTeacherQueue(centerId);
      }
      setEvents(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [centerId, role, view]);

  useEffect(() => {
    loadEvents();
    if (view === 'pending') {
      const interval = setInterval(loadEvents, 15000);
      return () => clearInterval(interval);
    }
  }, [loadEvents, view]);

  // ─── Actions ───────────────────────────────────────────────
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
      if (action === 'approve' || action === 'reject') {
        setEvents((prev) => prev.filter((e) => e.id !== eventId));
      } else {
        await loadEvents();
      }
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

  // ─── Grouping ──────────────────────────────────────────────
  const grouped = events.reduce((acc, event) => {
    const name = event.child_name || 'Unknown';
    if (!acc[name]) acc[name] = [];
    acc[name].push(event);
    return acc;
  }, {});

  const isHistory = view === 'history';
  const nav = role === 'director' ? DIRECTOR_NAV : TEACHER_NAV;

  const headerTitle = role === 'director' ? 'Director Dashboard' : 'Teacher Console';
  const headerSubtitle = role === 'director' ? null : '— Room 2';

  // Hero section copy per view/role
  const heroHeadline = isHistory ? 'Review History' : role === 'director' ? 'Needs Attention' : 'Daily Digest';
  const heroDesc = isHistory
    ? 'Browse previously reviewed events and their outcomes.'
    : role === 'director'
    ? `${events.length} flagged event${events.length !== 1 ? 's' : ''} need your attention today.`
    : `AI has curated ${events.length} ${events.length === 1 ? 'activity' : 'activities'} today. Review and publish to parent feeds with one tap.`;

  return (
    <div className="min-h-screen bg-surface">
      {/* ── Top App Bar ── */}
      <header className="bg-surface/80 backdrop-blur-xl flex justify-between items-center w-full px-6 py-4 fixed top-0 z-50 border-b border-outline-variant/10">
        <div className="flex items-center gap-3">
          {/* Role avatar / switcher */}
          <button
            onClick={() => setRole(role === 'teacher' ? 'director' : 'teacher')}
            title={`Switch to ${role === 'teacher' ? 'Director' : 'Teacher'} view`}
            className="w-10 h-10 rounded-full bg-surface-container-high flex items-center justify-center text-primary font-semibold text-sm border border-outline-variant/15 hover:bg-surface-container-highest transition-colors"
          >
            {role === 'teacher' ? 'T' : 'D'}
          </button>
          <div>
            <h1 className="font-headline text-xl font-semibold tracking-tight text-primary leading-tight">
              {headerTitle}
              {headerSubtitle && (
                <span className="text-on-surface-variant font-normal ml-1 text-base">{headerSubtitle}</span>
              )}
            </h1>
          </div>
        </div>
        <button
          onClick={loadEvents}
          disabled={loading}
          className="text-primary hover:opacity-70 transition-opacity disabled:opacity-40"
          title="Refresh"
        >
          <span className="material-symbols-outlined">sync_alt</span>
        </button>
      </header>

      {/* ── Main Content ── */}
      <main className="pt-24 pb-32 px-6 max-w-4xl mx-auto">
        {/* Error banner */}
        {error && (
          <div className="mb-6 flex items-center justify-between bg-error-container text-on-error-container px-4 py-3 rounded-lg">
            <span className="text-sm">{error}</span>
            <button onClick={() => setError(null)} className="ml-3 hover:opacity-70">
              <span className="material-symbols-outlined text-base">close</span>
            </button>
          </div>
        )}

        {view === 'activity' ? (
          <ActivityLog centerId={centerId} />
        ) : loading && events.length === 0 ? (
          /* Loading state */
          <div className="flex flex-col items-center justify-center py-24 gap-4 text-on-surface-variant">
            <div className="spinner" />
            <p className="text-sm font-medium">Loading events…</p>
          </div>
        ) : (
          <>
            {/* Hero Section */}
            <section className="mb-10">
              <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
                <div>
                  <h2 className="font-headline text-4xl md:text-5xl text-on-surface mb-2 tracking-tight">
                    {heroHeadline}
                  </h2>
                  <p className="text-on-surface-variant max-w-md leading-relaxed">{heroDesc}</p>
                </div>
                {!isHistory && events.length > 0 && (
                  <div className="flex gap-2 shrink-0">
                    <span className="ai-chip">
                      <span className="material-symbols-outlined text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>
                        auto_awesome
                      </span>
                      {events.length} Ready to Publish
                    </span>
                  </div>
                )}
              </div>
            </section>

            {/* Events */}
            {events.length === 0 ? (
              <EmptyState role={isHistory ? 'history' : role} />
            ) : (
              <div className="space-y-10">
                {Object.entries(grouped).map(([childName, childEvents]) => (
                  <section key={childName} className="space-y-4">
                    {/* Child group header */}
                    <div className="flex items-center gap-4 px-2">
                      <div className="w-11 h-11 rounded-full bg-surface-container-highest flex items-center justify-center text-primary font-semibold text-base border border-outline-variant/15 shrink-0">
                        {childName.charAt(0).toUpperCase()}
                      </div>
                      <h3 className="font-headline text-2xl text-on-surface">{childName}</h3>
                      <span className="ml-1 text-xs font-medium text-on-surface-variant bg-surface-container px-2.5 py-1 rounded-full">
                        {childEvents.length}
                      </span>
                      {!isHistory && childEvents.length > 1 && (
                        <button
                          onClick={() => handleBatchApprove(childName)}
                          className="ml-auto ai-chip text-xs"
                        >
                          <span className="material-symbols-outlined text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>
                            done_all
                          </span>
                          Approve All
                        </button>
                      )}
                    </div>

                    {/* Event cards */}
                    <div className="space-y-4">
                      {childEvents.map((event) => (
                        <EventCard
                          key={event.id}
                          event={event}
                          centerId={centerId}
                          onAction={handleAction}
                          readOnly={isHistory}
                        />
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            )}
          </>
        )}
      </main>

      {/* ── Bottom Nav ── */}
      <nav className="fixed bottom-0 left-0 w-full flex justify-around items-center px-4 pb-6 pt-3 glass-panel z-50 rounded-t-lg shadow-ambient-up border-t border-outline-variant/15">
        {nav.map((item) => {
          const isActive = view === item.key;
          return (
            <button
              key={item.key}
              onClick={() => setView(item.key)}
              className={`flex flex-col items-center justify-center px-5 py-2 transition-all duration-200 active:scale-90 ${
                isActive
                  ? 'bg-gradient-to-br from-[#8a4f36] to-[#d38b6e] text-white rounded-full'
                  : 'text-outline hover:text-primary'
              }`}
            >
              <span
                className="material-symbols-outlined"
                style={isActive ? { fontVariationSettings: "'FILL' 1" } : {}}
              >
                {item.icon}
              </span>
              <span className="text-[10px] font-medium tracking-wide uppercase mt-1">{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* ── Toasts ── */}
      <div className="fixed bottom-28 right-6 z-[100] flex flex-col gap-2">
        {toasts.map((toast) => (
          <Toast
            key={toast.id}
            message={toast.message}
            type={toast.type}
            onClose={() => removeToast(toast.id)}
          />
        ))}
      </div>
    </div>
  );
}

export default App;

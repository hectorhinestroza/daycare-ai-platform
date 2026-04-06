import { useState, useEffect, useCallback } from 'react';
import EventCard from './components/EventCard';
import EmptyState from './components/EmptyState';
import Toast from './components/Toast';
import {
  fetchTeacherQueue,
  fetchDirectorQueue,
  fetchHistory,
  approveEvent,
  rejectEvent,
  editEvent,
  batchApprove,
} from './api';

function App() {
  const [role, setRole] = useState('teacher');
  const [view, setView] = useState('pending'); // 'pending' | 'history'
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [toasts, setToasts] = useState([]);

  const params = new URLSearchParams(window.location.search);
  const centerId = params.get('center') || '';

  // ─── Toast helpers ────────────────────────────────────────
  function addToast(message, type = 'success') {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
  }

  function removeToast(id) {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }

  // ─── Data loading ─────────────────────────────────────────
  const loadEvents = useCallback(async () => {
    if (!centerId) {
      setError('No center_id provided. Add ?center=YOUR_CENTER_ID to the URL.');
      setLoading(false);
      return;
    }

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

  // ─── Actions ──────────────────────────────────────────────
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

  // ─── Grouping ─────────────────────────────────────────────
  const grouped = events.reduce((acc, event) => {
    const name = event.child_name || 'Unknown';
    if (!acc[name]) acc[name] = [];
    acc[name].push(event);
    return acc;
  }, {});

  const isHistory = view === 'history';

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1>📋 Review Console</h1>
          <span className="event-count">
            {events.length} {isHistory ? 'reviewed' : 'pending'}
          </span>
        </div>
        <div className="header-right">
          <div className="view-toggle">
            <button
              className={`toggle-btn ${view === 'pending' ? 'active' : ''}`}
              onClick={() => setView('pending')}
            >
              📥 Pending
            </button>
            <button
              className={`toggle-btn ${view === 'history' ? 'active' : ''}`}
              onClick={() => setView('history')}
            >
              📜 History
            </button>
          </div>
          {!isHistory && (
            <div className="role-toggle">
              <button
                className={`toggle-btn ${role === 'teacher' ? 'active' : ''}`}
                onClick={() => setRole('teacher')}
              >
                👩‍🏫 Teacher
              </button>
              <button
                className={`toggle-btn ${role === 'director' ? 'active' : ''}`}
                onClick={() => setRole('director')}
              >
                👔 Director
              </button>
            </div>
          )}
          <button className="btn btn-refresh" onClick={loadEvents} disabled={loading}>
            🔄
          </button>
        </div>
      </header>

      <main className="app-main">
        {error && (
          <div className="error-banner">
            <span>⚠️ {error}</span>
            <button onClick={() => setError(null)}>✕</button>
          </div>
        )}

        {loading && events.length === 0 ? (
          <div className="loading-state">
            <div className="spinner" />
            <p>Loading events...</p>
          </div>
        ) : events.length === 0 ? (
          <EmptyState role={isHistory ? 'history' : role} />
        ) : (
          <div className="event-groups">
            {Object.entries(grouped).map(([childName, childEvents]) => (
              <section key={childName} className="child-group">
                <h2 className="group-header">
                  <span className="child-avatar">
                    {childName.charAt(0).toUpperCase()}
                  </span>
                  {childName}
                  <span className="group-count">{childEvents.length}</span>
                  {!isHistory && childEvents.length > 1 && (
                    <button
                      className="btn btn-batch-approve"
                      onClick={() => handleBatchApprove(childName)}
                    >
                      ✅ Approve All
                    </button>
                  )}
                </h2>
                <div className="cards-list">
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
      </main>

      {/* Toast notifications */}
      <div className="toast-container">
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

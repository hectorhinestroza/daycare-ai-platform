import { useState, useEffect, useCallback } from 'react';
import EventCard from './components/EventCard';
import EmptyState from './components/EmptyState';
import {
  fetchTeacherQueue,
  fetchDirectorQueue,
  approveEvent,
  rejectEvent,
  editEvent,
} from './api';

function App() {
  const [role, setRole] = useState('teacher');
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Read center_id from URL params (e.g., ?center=uuid)
  const params = new URLSearchParams(window.location.search);
  const centerId = params.get('center') || '';

  const loadEvents = useCallback(async () => {
    if (!centerId) {
      setError('No center_id provided. Add ?center=YOUR_CENTER_ID to the URL.');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data =
        role === 'director'
          ? await fetchDirectorQueue(centerId)
          : await fetchTeacherQueue(centerId);
      setEvents(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [centerId, role]);

  useEffect(() => {
    loadEvents();

    // Auto-refresh every 15 seconds
    const interval = setInterval(loadEvents, 15000);
    return () => clearInterval(interval);
  }, [loadEvents]);

  async function handleAction(action, eventId, editData) {
    try {
      if (action === 'approve') {
        await approveEvent(centerId, eventId);
      } else if (action === 'reject') {
        await rejectEvent(centerId, eventId);
      } else if (action === 'edit') {
        await editEvent(centerId, eventId, editData);
      }
      // Remove the event from the list (or refresh)
      if (action === 'approve' || action === 'reject') {
        setEvents((prev) => prev.filter((e) => e.id !== eventId));
      } else {
        await loadEvents();
      }
    } catch (err) {
      setError(err.message);
    }
  }

  // Group events by child name
  const grouped = events.reduce((acc, event) => {
    const name = event.child_name || 'Unknown';
    if (!acc[name]) acc[name] = [];
    acc[name].push(event);
    return acc;
  }, {});

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1>📋 Review Console</h1>
          <span className="event-count">
            {events.length} pending
          </span>
        </div>
        <div className="header-right">
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
          <EmptyState role={role} />
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
                </h2>
                <div className="cards-list">
                  {childEvents.map((event) => (
                    <EventCard
                      key={event.id}
                      event={event}
                      centerId={centerId}
                      onAction={handleAction}
                    />
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

export default App;

import { useState, useEffect, useCallback } from 'react';
import EventCard from './EventCard';
import EmptyState from '../../components/ui/EmptyState';
import { fetchHistory, fetchTeachers } from '../../api';

function GroupHeader({ name, count }) {
  return (
    <div className="flex items-center gap-4 px-2">
      <div className="w-11 h-11 rounded-full bg-surface-container-highest flex items-center justify-center text-primary font-semibold text-base border border-outline-variant/15 shrink-0">
        {name.charAt(0).toUpperCase()}
      </div>
      <h3 className="font-headline text-2xl text-on-surface">{name}</h3>
      <span className="ml-1 text-xs font-medium text-on-surface-variant bg-surface-container px-2.5 py-1 rounded-full">
        {count}
      </span>
    </div>
  );
}

function ChildSubGroup({ childName, events }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 px-2 pt-2">
        <div className="w-8 h-8 rounded-full bg-secondary-fixed flex items-center justify-center text-on-secondary-fixed-variant font-semibold text-sm shrink-0">
          {childName.charAt(0).toUpperCase()}
        </div>
        <span className="font-medium text-on-surface">{childName}</span>
        <span className="text-xs text-on-surface-variant bg-surface-container px-2 py-0.5 rounded-full">
          {events.length}
        </span>
      </div>
      <div className="space-y-3 pl-4 border-l-2 border-outline-variant/15 ml-6">
        {events.map((event) => (
          <div key={event.id}>
            <EventCard event={event} readOnly />
            <div className="flex items-center gap-2 px-3 pt-1.5 pb-1 flex-wrap">
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
    </div>
  );
}

export default function DirectorHistoryView({ centerId }) {
  const [events, setEvents] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [groupBy, setGroupBy] = useState('child'); // 'child' | 'teacher'
  const [selectedFilter, setSelectedFilter] = useState(''); // '' = All

  const loadData = useCallback(async () => {
    if (!centerId) return;
    setLoading(true);
    setError(null);
    try {
      const [eventsData, teachersData] = await Promise.all([
        fetchHistory(centerId, { limit: 500 }),
        fetchTeachers(centerId),
      ]);
      setEvents(eventsData);
      setTeachers(teachersData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [centerId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // By Child: flat grouping by child_name
  const byChild = events.reduce((acc, event) => {
    const key = event.child_name || 'Unknown';
    if (!acc[key]) acc[key] = [];
    acc[key].push(event);
    return acc;
  }, {});

  // By Teacher: two-level — teacher → children → events
  const byTeacher = events.reduce((acc, event) => {
    const teacher = event.teacher_name || 'System';
    const child = event.child_name || 'Unknown';
    if (!acc[teacher]) acc[teacher] = {};
    if (!acc[teacher][child]) acc[teacher][child] = [];
    acc[teacher][child].push(event);
    return acc;
  }, {});

  const filterOptions = groupBy === 'teacher'
    ? teachers.map((t) => t.name).sort()
    : Object.keys(byChild).sort();

  const visibleByChild = selectedFilter
    ? Object.fromEntries(Object.entries(byChild).filter(([k]) => k === selectedFilter))
    : byChild;

  const visibleByTeacher = selectedFilter
    ? Object.fromEntries(Object.entries(byTeacher).filter(([k]) => k === selectedFilter))
    : byTeacher;

  function handleGroupByChange(next) {
    setGroupBy(next);
    setSelectedFilter('');
  }

  const isEmpty = groupBy === 'teacher'
    ? Object.keys(visibleByTeacher).length === 0
    : Object.keys(visibleByChild).length === 0;

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

          <div className="flex items-center gap-3 shrink-0 flex-wrap">
            {/* Group-by toggle */}
            <div className="flex items-center gap-1 bg-surface-container rounded-full p-1">
              <button
                onClick={() => handleGroupByChange('child')}
                className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all duration-200 ${
                  groupBy === 'child'
                    ? 'bg-primary text-on-primary shadow-sm'
                    : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                By Child
              </button>
              <button
                onClick={() => handleGroupByChange('teacher')}
                className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all duration-200 ${
                  groupBy === 'teacher'
                    ? 'bg-primary text-on-primary shadow-sm'
                    : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                By Teacher
              </button>
            </div>

            {/* Filter dropdown */}
            {filterOptions.length > 0 && (
              <select
                value={selectedFilter}
                onChange={(e) => setSelectedFilter(e.target.value)}
                className="bg-surface-container text-on-surface text-sm rounded-full px-4 py-2 border border-outline-variant/20 outline-none focus:border-outline-variant/50 transition-colors cursor-pointer"
              >
                <option value="">
                  {groupBy === 'child' ? 'All Children' : 'All Teachers'}
                </option>
                {filterOptions.map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            )}
          </div>
        </div>
      </section>

      {events.length === 0 ? (
        <EmptyState role="history" />
      ) : isEmpty ? (
        <div className="flex flex-col items-center justify-center py-24 gap-3 text-on-surface-variant">
          <span className="material-symbols-outlined text-4xl">inbox</span>
          <p className="text-sm font-medium">No events logged yet</p>
        </div>
      ) : groupBy === 'teacher' ? (
        /* ── By Teacher: teacher → children → events ── */
        <div className="space-y-10">
          {Object.entries(visibleByTeacher).map(([teacherName, childMap]) => {
            const totalEvents = Object.values(childMap).reduce((s, evts) => s + evts.length, 0);
            return (
              <section key={teacherName} className="space-y-4">
                <GroupHeader name={teacherName} count={totalEvents} />
                <div className="space-y-6 pl-2">
                  {Object.entries(childMap).map(([childName, childEvents]) => (
                    <ChildSubGroup key={childName} childName={childName} events={childEvents} />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      ) : (
        /* ── By Child: flat events per child with teacher attribution ── */
        <div className="space-y-10">
          {Object.entries(visibleByChild).map(([childName, childEvents]) => (
            <section key={childName} className="space-y-4">
              <GroupHeader name={childName} count={childEvents.length} />
              <div className="space-y-4">
                {childEvents.map((event) => (
                  <div key={event.id}>
                    <EventCard event={event} readOnly />
                    <div className="flex items-center gap-2 px-3 pt-2 pb-1 flex-wrap">
                      {event.teacher_name && (
                        <span className="text-xs text-on-surface-variant">
                          Logged by{' '}
                          <span className="font-medium text-on-surface">{event.teacher_name}</span>
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

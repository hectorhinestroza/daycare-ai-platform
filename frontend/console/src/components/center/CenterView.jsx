import { useState, useEffect, useCallback } from 'react';
import { fetchRooms, fetchTeachers } from '../../api';
import ChildrenPanel from './ChildrenPanel';
import RoomsPanel from './RoomsPanel';

const SUB_TABS = [
  { key: 'children', label: 'Children', icon: 'child_care' },
  { key: 'rooms',    label: 'Rooms',    icon: 'meeting_room' },
];

export default function CenterView({ centerId, addToast }) {
  const [subView, setSubView] = useState('children');
  const [rooms, setRooms] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadSharedData = useCallback(async () => {
    if (!centerId) return;
    setLoading(true);
    try {
      const [roomsData, teachersData] = await Promise.all([
        fetchRooms(centerId),
        fetchTeachers(centerId),
      ]);
      setRooms(roomsData);
      setTeachers(teachersData);
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [centerId, addToast]);

  useEffect(() => { loadSharedData(); }, [loadSharedData]);

  return (
    <>
      {/* Hero */}
      <section className="mb-8">
        <h2 className="font-headline text-4xl md:text-5xl text-on-surface mb-2 tracking-tight">
          Manage Center
        </h2>
        <p className="text-on-surface-variant max-w-md leading-relaxed">
          Classrooms, children, and parent contacts for your center.
        </p>
      </section>

      {/* Sub-nav tabs */}
      <div className="flex gap-2 mb-8">
        {SUB_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setSubView(tab.key)}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium transition-all duration-200 ${
              subView === tab.key
                ? 'bg-gradient-to-br from-[#8a4f36] to-[#d38b6e] text-white shadow-lg'
                : 'bg-surface-container-low text-on-surface-variant hover:bg-surface-container-high'
            }`}
          >
            <span className="material-symbols-outlined text-base" style={subView === tab.key ? { fontVariationSettings: "'FILL' 1" } : {}}>
              {tab.icon}
            </span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-24 gap-4 text-on-surface-variant">
          <div className="spinner" />
          <p className="text-sm font-medium">Loading center data…</p>
        </div>
      ) : subView === 'children' ? (
        <ChildrenPanel
          centerId={centerId}
          rooms={rooms}
          addToast={addToast}
        />
      ) : (
        <RoomsPanel
          centerId={centerId}
          rooms={rooms}
          teachers={teachers}
          addToast={addToast}
          onRoomsChange={loadSharedData}
        />
      )}
    </>
  );
}

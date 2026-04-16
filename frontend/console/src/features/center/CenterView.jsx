import { useState, useEffect, useCallback } from 'react';
import { fetchRooms, fetchTeachers, generateAllNarratives } from '../../api';
import ChildrenPanel from './ChildrenPanel';
import RoomsPanel from './RoomsPanel';
import TeachersPanel from './TeachersPanel';

const SUB_TABS = [
  { key: 'children', label: 'Children',  icon: 'child_care' },
  { key: 'rooms',    label: 'Rooms',     icon: 'meeting_room' },
  { key: 'teachers', label: 'Teachers',  icon: 'school' },
];

export default function CenterView({ centerId, addToast }) {
  const [subView, setSubView] = useState('children');
  const [rooms, setRooms] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generatingEOD, setGeneratingEOD] = useState(false);

  async function handleGenerateEOD() {
    setGeneratingEOD(true);
    try {
      const result = await generateAllNarratives(centerId);
      addToast(
        `EOD reports: ${result.generated} generated, ${result.failed} failed, ${result.skipped} skipped`,
        result.failed > 0 ? 'error' : 'success',
      );
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setGeneratingEOD(false);
    }
  }

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
      <section className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h2 className="font-headline text-4xl md:text-5xl text-on-surface mb-2 tracking-tight">
            Manage Center
          </h2>
          <p className="text-on-surface-variant max-w-md leading-relaxed">
            Classrooms, children, and parent contacts for your center.
          </p>
        </div>
        <button
          onClick={handleGenerateEOD}
          disabled={generatingEOD}
          className="btn-secondary flex items-center gap-2 shrink-0 disabled:opacity-60 disabled:cursor-not-allowed"
          title="Generate end-of-day summaries for all active children"
        >
          <span
            className={`material-symbols-outlined text-base ${generatingEOD ? 'animate-spin' : ''}`}
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            {generatingEOD ? 'progress_activity' : 'auto_awesome'}
          </span>
          {generatingEOD ? 'Generating…' : 'EOD Reports'}
        </button>
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
      ) : subView === 'teachers' ? (
        <TeachersPanel
          centerId={centerId}
          rooms={rooms}
          teachers={teachers}
          addToast={addToast}
          onTeachersChange={loadSharedData}
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

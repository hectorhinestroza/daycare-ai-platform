import { useState, useEffect } from 'react';
import TeacherQueue from './portals/teacher/TeacherQueue';
import DirectorDashboard from './portals/director/DirectorDashboard';
import HistoryView from './features/events/HistoryView';
import ActivityLog from './features/events/ActivityLog';
import CenterView from './features/center/CenterView';
import Toast from './components/ui/Toast';

// Bottom nav config per role
const TEACHER_NAV = [
  { key: 'pending',  icon: 'auto_awesome', label: 'Today' },
  { key: 'history',  icon: 'history',      label: 'History' },
];

const DIRECTOR_NAV = [
  { key: 'pending',  icon: 'auto_awesome', label: 'Queue' },
  { key: 'history',  icon: 'history',      label: 'History' },
  { key: 'center',   icon: 'apartment',    label: 'Center' },
  { key: 'activity', icon: 'bar_chart',    label: 'Activity' },
];

function App({ forcedRole, centerId: propscenterId }) {
  const [role, setRole] = useState(forcedRole || 'teacher');
  const [view, setView] = useState('pending');
  const [toasts, setToasts] = useState([]);

  const params = new URLSearchParams(window.location.search);
  const centerId = propscenterId || params.get('center') || '';
  const isRouted = !!forcedRole;

  // Enforce role-based view access
  useEffect(() => {
    if (role === 'teacher' && (view === 'activity' || view === 'center')) {
      setView('pending');
    }
  }, [role, view]);

  // Toast Helpers
  function addToast(message, type = 'success') {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
  }

  function removeToast(id) {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }

  const nav = role === 'director' ? DIRECTOR_NAV : TEACHER_NAV;
  const headerTitle = role === 'director' ? 'Director Dashboard' : 'Teacher Console';
  const headerSubtitle = role === 'director' ? null : '— Room 2';

  return (
    <div className="min-h-screen bg-surface">
      {/* ── Top App Bar ── */}
      <header className="bg-surface/80 backdrop-blur-xl flex justify-between items-center w-full px-6 py-4 fixed top-0 z-50">
        <div className="flex items-center gap-3">
          {/* Role avatar / switcher */}
          <button
            onClick={() => setRole(role === 'teacher' ? 'director' : 'teacher')}
            title={`Switch to ${role === 'teacher' ? 'Director' : 'Teacher'} view`}
            className="w-10 h-10 rounded-full bg-surface-container flex items-center justify-center text-primary font-semibold text-sm border border-outline-variant/5 hover:bg-surface-container-high transition-all active:scale-95"
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
      </header>

      {/* ── Main Content ── */}
      <main className="pt-24 pb-32 px-6 max-w-4xl mx-auto">
        {view === 'center' && role === 'director' && <CenterView centerId={centerId} addToast={addToast} />}
        {view === 'activity' && role === 'director' && <ActivityLog centerId={centerId} />}
        {view === 'history' && <HistoryView centerId={centerId} addToast={addToast} />}
        {view === 'pending' && role === 'director' && <DirectorDashboard centerId={centerId} addToast={addToast} />}
        {view === 'pending' && role === 'teacher' && <TeacherQueue centerId={centerId} addToast={addToast} />}
      </main>

      {/* ── Bottom Nav ── */}
      <nav className="fixed bottom-0 left-0 w-full flex justify-around items-center px-4 pb-8 pt-4 glass-panel z-50 rounded-t-[2.5rem] shadow-ambient-up">
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

import ChildProfile from './ChildProfile';

const STATUS_STYLE = {
  ACTIVE:     'bg-secondary-fixed text-on-secondary-fixed-variant',
  ENROLLED:   'bg-primary-fixed text-on-primary-container',
  WAITLIST:   'bg-tertiary-fixed text-on-tertiary-fixed-variant',
  UNENROLLED: 'bg-surface-container-high text-on-surface-variant',
};

function computeAge(dob) {
  if (!dob) return null;
  const birth = new Date(dob);
  const now = new Date();
  let years = now.getFullYear() - birth.getFullYear();
  let months = now.getMonth() - birth.getMonth();
  if (months < 0) { years--; months += 12; }
  if (years > 0) return `${years}y ${months}m`;
  return `${months}m`;
}

export default function ChildCard({ child, rooms, expanded, onToggle, centerId, addToast, onUpdate }) {
  const roomName = rooms.find((r) => r.id === child.room_id)?.name;
  const age = computeAge(child.dob);
  const statusStyle = STATUS_STYLE[child.status] || STATUS_STYLE.ENROLLED;

  return (
    <div className="japandi-card rounded-lg shadow-ambient border border-outline-variant/10 overflow-hidden card-appear">
      {/* Collapsed summary row */}
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-4 p-5 text-left hover:bg-surface-container-low/50 transition-colors"
      >
        <div className="w-10 h-10 rounded-full bg-surface-container-highest flex items-center justify-center text-primary font-semibold text-sm shrink-0 border border-outline-variant/15">
          {child.name.charAt(0).toUpperCase()}
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="font-semibold text-on-surface truncate">{child.name}</h4>
          <div className="flex items-center gap-2 mt-0.5">
            {roomName && <span className="text-xs text-on-surface-variant">{roomName}</span>}
            {roomName && age && <span className="text-xs text-on-surface-variant/40">·</span>}
            {age && <span className="text-xs text-on-surface-variant">{age}</span>}
          </div>
        </div>
        <span className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full ${statusStyle}`}>
          {child.status}
        </span>
        <span className="material-symbols-outlined text-outline text-lg transition-transform duration-200" style={{ transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)' }}>
          expand_more
        </span>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="expand-appear border-t border-outline-variant/10">
          <ChildProfile
            child={child}
            rooms={rooms}
            centerId={centerId}
            addToast={addToast}
            onUpdate={onUpdate}
          />
        </div>
      )}
    </div>
  );
}

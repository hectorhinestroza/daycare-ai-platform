import { useState, useEffect, useCallback } from 'react';
import { fetchChildren } from '../../api';
import ChildCard from './ChildCard';
import AddChildModal from './AddChildModal';

const STATUS_OPTIONS = ['ACTIVE', 'ENROLLED', 'WAITLIST'];

export default function ChildrenPanel({ centerId, rooms, addToast }) {
  const [children, setChildren] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterRoom, setFilterRoom] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [expandedId, setExpandedId] = useState(null);
  const [showAddModal, setShowAddModal] = useState(false);

  const loadChildren = useCallback(async () => {
    if (!centerId) return;
    setLoading(true);
    try {
      const filters = {};
      if (filterRoom) filters.room_id = filterRoom;
      if (filterStatus) filters.status = filterStatus;
      const data = await fetchChildren(centerId, filters);
      setChildren(data);
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [centerId, filterRoom, filterStatus, addToast]);

  useEffect(() => { loadChildren(); }, [loadChildren]);

  const filtered = searchTerm
    ? children.filter((c) => c.name.toLowerCase().includes(searchTerm.toLowerCase()))
    : children;

  return (
    <div>
      {/* Filter bar */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        {/* Search */}
        <div className="relative flex-1">
          <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-outline text-lg">search</span>
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search children…"
            className="w-full bg-surface-container-highest rounded-full pl-11 pr-4 py-3 text-on-surface placeholder:text-outline outline-none focus:bg-surface-container-lowest border border-transparent focus:border-outline-variant/20 transition-colors"
          />
        </div>

        {/* Room filter */}
        <select
          value={filterRoom}
          onChange={(e) => setFilterRoom(e.target.value)}
          className="bg-surface-container-highest rounded-full px-4 py-3 text-on-surface-variant text-sm outline-none focus:bg-surface-container-lowest border border-transparent focus:border-outline-variant/20 transition-colors appearance-none cursor-pointer"
        >
          <option value="">All Rooms</option>
          {rooms.map((r) => (
            <option key={r.id} value={r.id}>{r.name}</option>
          ))}
        </select>

        {/* Status pills */}
        <div className="flex gap-1.5 items-center">
          {STATUS_OPTIONS.map((s) => (
            <button
              key={s}
              onClick={() => setFilterStatus(filterStatus === s ? '' : s)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                filterStatus === s
                  ? 'bg-primary text-white'
                  : 'bg-surface-container-low text-on-surface-variant hover:bg-surface-container-high'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Action bar */}
      <div className="flex items-center justify-between mb-6">
        <span className="text-sm text-on-surface-variant">
          {filtered.length} {filtered.length === 1 ? 'child' : 'children'}
        </span>
        <button onClick={() => setShowAddModal(true)} className="btn-primary !py-2.5 !px-5 text-sm">
          <span className="material-symbols-outlined text-base mr-1">person_add</span>
          Enroll Child
        </button>
      </div>

      {/* Children list */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-16 gap-4 text-on-surface-variant">
          <div className="spinner" />
          <p className="text-sm font-medium">Loading children…</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-on-surface-variant">
          <span className="material-symbols-outlined text-4xl text-outline mb-3 block">child_care</span>
          <p className="font-medium">{children.length === 0 ? 'No children enrolled' : 'No matches'}</p>
          <p className="text-sm mt-1">
            {children.length === 0 ? 'Enroll your first child to get started.' : 'Try adjusting your search or filters.'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((child) => (
            <ChildCard
              key={child.id}
              child={child}
              rooms={rooms}
              expanded={expandedId === child.id}
              onToggle={() => setExpandedId(expandedId === child.id ? null : child.id)}
              centerId={centerId}
              addToast={addToast}
              onUpdate={loadChildren}
            />
          ))}
        </div>
      )}

      {/* Add child modal */}
      {showAddModal && (
        <AddChildModal
          centerId={centerId}
          rooms={rooms}
          addToast={addToast}
          onClose={() => setShowAddModal(false)}
          onCreated={() => { setShowAddModal(false); loadChildren(); }}
        />
      )}
    </div>
  );
}

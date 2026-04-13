import { useState } from 'react';
import { createTeacher, updateTeacher } from '../../api';

export default function TeachersPanel({ centerId, rooms, teachers, addToast, onTeachersChange }) {
  const [showAdd, setShowAdd] = useState(false);
  const [newTeacher, setNewTeacher] = useState({ name: '', phone: '', room_id: '' });
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editFields, setEditFields] = useState({});

  async function handleAdd(e) {
    e.preventDefault();
    if (!newTeacher.name.trim() || !newTeacher.phone.trim()) return;
    setSaving(true);
    try {
      const data = { name: newTeacher.name.trim(), phone: newTeacher.phone.trim() };
      if (newTeacher.room_id) data.room_id = newTeacher.room_id;
      await createTeacher(centerId, data);
      addToast(`${data.name} added`);
      setNewTeacher({ name: '', phone: '', room_id: '' });
      setShowAdd(false);
      onTeachersChange();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSaving(false);
    }
  }

  function startEdit(teacher) {
    setEditFields({
      name: teacher.name,
      phone: teacher.phone,
      room_id: teacher.room_id || '',
      is_active: teacher.is_active,
    });
    setEditingId(teacher.id);
  }

  async function saveEdit(teacherId) {
    const teacher = teachers.find((t) => t.id === teacherId);
    const updates = {};
    if (editFields.name !== teacher.name) updates.name = editFields.name;
    if (editFields.phone !== teacher.phone) updates.phone = editFields.phone;
    if (editFields.room_id !== (teacher.room_id || '')) updates.room_id = editFields.room_id || null;
    if (editFields.is_active !== teacher.is_active) updates.is_active = editFields.is_active;

    if (Object.keys(updates).length === 0) {
      setEditingId(null);
      return;
    }
    setSaving(true);
    try {
      await updateTeacher(centerId, teacherId, updates);
      addToast('Teacher updated');
      setEditingId(null);
      onTeachersChange();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSaving(false);
    }
  }

  const inputClass = 'w-full bg-surface-container-highest rounded px-4 py-2.5 text-sm text-on-surface outline-none focus:bg-surface-container-lowest border border-transparent focus:border-outline-variant/20 transition-colors';

  return (
    <div>
      {/* Action bar */}
      <div className="flex items-center justify-between mb-6">
        <span className="text-sm text-on-surface-variant">
          {teachers.length} {teachers.length === 1 ? 'teacher' : 'teachers'}
        </span>
        {!showAdd && (
          <button onClick={() => setShowAdd(true)} className="btn-primary !py-2.5 !px-5 text-sm">
            <span className="material-symbols-outlined text-base mr-1">person_add</span>
            Add Teacher
          </button>
        )}
      </div>

      {/* Add teacher form */}
      {showAdd && (
        <form onSubmit={handleAdd} className="japandi-card rounded-lg shadow-ambient p-5 mb-6 card-appear">
          <h4 className="font-headline text-lg text-on-surface mb-4">New Teacher</h4>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="text-xs font-medium text-on-surface-variant mb-1.5 block">Name *</label>
              <input
                type="text"
                value={newTeacher.name}
                onChange={(e) => setNewTeacher({ ...newTeacher, name: e.target.value })}
                placeholder="Full name"
                className={inputClass}
                required
                autoFocus
              />
            </div>
            <div>
              <label className="text-xs font-medium text-on-surface-variant mb-1.5 block">WhatsApp Phone *</label>
              <input
                type="tel"
                value={newTeacher.phone}
                onChange={(e) => setNewTeacher({ ...newTeacher, phone: e.target.value })}
                placeholder="+1 555-0100"
                className={inputClass}
                required
              />
            </div>
            <div>
              <label className="text-xs font-medium text-on-surface-variant mb-1.5 block">Classroom</label>
              <select
                value={newTeacher.room_id}
                onChange={(e) => setNewTeacher({ ...newTeacher, room_id: e.target.value })}
                className={inputClass}
              >
                <option value="">Unassigned</option>
                {rooms.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </div>
          </div>
          <div className="flex gap-3 justify-end pt-4">
            <button type="button" onClick={() => setShowAdd(false)} className="btn-secondary" disabled={saving}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={saving || !newTeacher.name.trim() || !newTeacher.phone.trim()}>
              {saving ? 'Adding...' : 'Add Teacher'}
            </button>
          </div>
        </form>
      )}

      {/* Teacher list */}
      {teachers.length === 0 ? (
        <div className="text-center py-16 text-on-surface-variant">
          <span className="material-symbols-outlined text-4xl text-outline mb-3 block">school</span>
          <p className="font-medium">No teachers added</p>
          <p className="text-sm mt-1">Add your first teacher to get started.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {teachers.map((teacher) => {
            const room = rooms.find((r) => r.id === teacher.room_id);
            const isEditing = editingId === teacher.id;

            if (isEditing) {
              return (
                <div key={teacher.id} className="japandi-card rounded-lg shadow-ambient p-5 card-appear">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <label className="text-xs font-medium text-on-surface-variant mb-1 block">Name</label>
                      <input
                        type="text"
                        value={editFields.name}
                        onChange={(e) => setEditFields({ ...editFields, name: e.target.value })}
                        className={inputClass}
                      />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-on-surface-variant mb-1 block">Phone</label>
                      <input
                        type="tel"
                        value={editFields.phone}
                        onChange={(e) => setEditFields({ ...editFields, phone: e.target.value })}
                        className={inputClass}
                      />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-on-surface-variant mb-1 block">Classroom</label>
                      <select
                        value={editFields.room_id}
                        onChange={(e) => setEditFields({ ...editFields, room_id: e.target.value })}
                        className={inputClass}
                      >
                        <option value="">Unassigned</option>
                        {rooms.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                      </select>
                    </div>
                  </div>
                  <div className="flex items-center gap-4 pt-3">
                    <label className="flex items-center gap-2 cursor-pointer text-sm">
                      <input
                        type="checkbox"
                        checked={editFields.is_active}
                        onChange={(e) => setEditFields({ ...editFields, is_active: e.target.checked })}
                        className="accent-primary"
                      />
                      <span className="text-on-surface-variant">Active</span>
                    </label>
                    <div className="ml-auto flex gap-2">
                      <button onClick={() => setEditingId(null)} className="btn-secondary !py-1.5 !px-4 text-xs" disabled={saving}>Cancel</button>
                      <button onClick={() => saveEdit(teacher.id)} className="btn-primary !py-1.5 !px-4 text-xs" disabled={saving}>Save</button>
                    </div>
                  </div>
                </div>
              );
            }

            return (
              <div key={teacher.id} className="japandi-card rounded-lg shadow-ambient p-5 flex items-center gap-4 group card-appear">
                {/* Avatar */}
                <div className={`w-11 h-11 rounded-full flex items-center justify-center text-sm font-semibold shrink-0 border border-outline-variant/15 ${
                  teacher.is_active
                    ? 'bg-secondary-fixed text-on-secondary-fixed-variant'
                    : 'bg-surface-container-high text-on-surface-variant'
                }`}>
                  {teacher.name.charAt(0).toUpperCase()}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h4 className="font-semibold text-on-surface truncate">{teacher.name}</h4>
                    {!teacher.is_active && (
                      <span className="text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant">
                        Inactive
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-0.5 text-xs text-on-surface-variant">
                    <span>{teacher.phone}</span>
                    {room && (
                      <>
                        <span className="text-on-surface-variant/40">·</span>
                        <span>{room.name}</span>
                      </>
                    )}
                  </div>
                </div>

                {/* Edit button */}
                <button
                  onClick={() => startEdit(teacher)}
                  className="opacity-0 group-hover:opacity-100 p-2 rounded-full hover:bg-surface-container-high text-outline transition-all"
                  title="Edit teacher"
                >
                  <span className="material-symbols-outlined text-base">edit</span>
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

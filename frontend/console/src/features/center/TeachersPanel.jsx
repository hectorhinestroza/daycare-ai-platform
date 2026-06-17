import { useEffect, useState } from 'react';
import { createTeacher, deleteTeacher, issueTeacherToken, updateTeacher } from '../../api';

export default function TeachersPanel({ centerId, rooms, teachers, addToast, onTeachersChange }) {
  const [showAdd, setShowAdd] = useState(false);
  const [newTeacher, setNewTeacher] = useState({ name: '', phone: '', room_ids: [], primary_room_id: '' });
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editFields, setEditFields] = useState({});
  // bootstrapUrls: { [teacherId]: string }  issuingFor: { [teacherId]: bool }
  const [bootstrapUrls, setBootstrapUrls] = useState({});
  const [issuingFor, setIssuingFor] = useState({});

  // Auto-mint a bootstrap URL for each teacher on first render.
  useEffect(() => {
    let cancelled = false;
    teachers.forEach((teacher) => {
      if (bootstrapUrls[teacher.id]) return;
      setIssuingFor((prev) => ({ ...prev, [teacher.id]: true }));
      issueTeacherToken({ centerId, teacherId: teacher.id })
        .then((result) => {
          if (!cancelled) setBootstrapUrls((prev) => ({ ...prev, [teacher.id]: result.bootstrap_url }));
        })
        .catch((err) => {
          if (!cancelled) addToast(err.message || 'Failed to mint teacher link', 'error');
        })
        .finally(() => {
          if (!cancelled) setIssuingFor((prev) => ({ ...prev, [teacher.id]: false }));
        });
    });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [teachers.map((t) => t.id).join(','), centerId]);

  async function regenerateTeacherUrl(teacher) {
    setIssuingFor((prev) => ({ ...prev, [teacher.id]: true }));
    setBootstrapUrls((prev) => ({ ...prev, [teacher.id]: null }));
    try {
      const result = await issueTeacherToken({ centerId, teacherId: teacher.id });
      setBootstrapUrls((prev) => ({ ...prev, [teacher.id]: result.bootstrap_url }));
    } catch (err) {
      addToast(err.message || 'Failed to mint teacher link', 'error');
    } finally {
      setIssuingFor((prev) => ({ ...prev, [teacher.id]: false }));
    }
  }

  function copyTeacherUrl(url) {
    navigator.clipboard.writeText(url).then(
      () => addToast('Copied!'),
      () => addToast('Copy blocked — long-press the URL to copy manually', 'error'),
    );
  }

  async function handleAdd(e) {
    e.preventDefault();
    if (!newTeacher.name.trim() || !newTeacher.phone.trim()) return;
    setSaving(true);
    try {
      const orderedRoomIds = [
        newTeacher.primary_room_id,
        ...newTeacher.room_ids.filter(id => id !== newTeacher.primary_room_id)
      ].filter(Boolean);
      const data = { 
        name: newTeacher.name.trim(), 
        phone: newTeacher.phone.trim(),
        room_ids: orderedRoomIds
      };
      await createTeacher(centerId, data);
      addToast(`${data.name} added`);
      setNewTeacher({ name: '', phone: '', room_ids: [], primary_room_id: '' });
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
      room_ids: teacher.room_ids || [],
      primary_room_id: teacher.room_id || '',
    });
    setEditingId(teacher.id);
  }

  async function saveEdit(teacherId) {
    const teacher = teachers.find((t) => t.id === teacherId);
    const updates = {};
    if (editFields.name !== teacher.name) updates.name = editFields.name;
    if (editFields.phone !== teacher.phone) updates.phone = editFields.phone;
    
    const orderedRoomIds = [
      editFields.primary_room_id,
      ...editFields.room_ids.filter(id => id !== editFields.primary_room_id)
    ].filter(Boolean);

    const currentOrderedRoomIds = [
      teacher.room_id,
      ...(teacher.room_ids || []).filter(id => id !== teacher.room_id)
    ].filter(Boolean);

    const changed = orderedRoomIds.length !== currentOrderedRoomIds.length ||
      orderedRoomIds.some((id, idx) => id !== currentOrderedRoomIds[idx]);

    if (changed) {
      updates.room_ids = orderedRoomIds;
    }

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

  async function removeTeacher(teacher) {
    if (!confirm(`Remove ${teacher.name}? They'll be hidden from the list and unable to post via WhatsApp. Their past events stay in the audit trail.`)) return;
    setSaving(true);
    try {
      await deleteTeacher(centerId, teacher.id);
      addToast(`${teacher.name} removed`);
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
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
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
          </div>
          
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
            <div className="sm:col-span-2">
              <label className="text-xs font-medium text-on-surface-variant mb-1.5 block">Classrooms</label>
              <div className="flex flex-wrap gap-2 p-3 bg-surface-container rounded-lg border border-outline-variant/10 min-h-[46px]">
                {rooms.length === 0 ? (
                  <span className="text-xs text-on-surface-variant">No classrooms available</span>
                ) : (
                  rooms.map((r) => {
                    const isChecked = (newTeacher.room_ids || []).includes(r.id);
                    return (
                      <label key={r.id} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border cursor-pointer select-none transition-all ${isChecked ? 'bg-primary-container text-on-primary-container border-primary' : 'bg-surface-container-high text-on-surface-variant border-outline-variant/30 hover:border-outline-variant/60'}`}>
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) => {
                            const updatedIds = e.target.checked
                              ? [...(newTeacher.room_ids || []), r.id]
                              : (newTeacher.room_ids || []).filter((id) => id !== r.id);
                            let updatedPrimary = newTeacher.primary_room_id;
                            if (!updatedIds.includes(updatedPrimary)) {
                              updatedPrimary = updatedIds[0] || '';
                            }
                            setNewTeacher({ ...newTeacher, room_ids: updatedIds, primary_room_id: updatedPrimary });
                          }}
                          className="sr-only"
                        />
                        {r.name}
                      </label>
                    );
                  })
                )}
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-on-surface-variant mb-1.5 block">Primary Classroom</label>
              <select
                value={newTeacher.primary_room_id}
                onChange={(e) => setNewTeacher({ ...newTeacher, primary_room_id: e.target.value })}
                disabled={!(newTeacher.room_ids && newTeacher.room_ids.length > 0)}
                className={`${inputClass} disabled:opacity-50`}
              >
                <option value="">Select primary...</option>
                {rooms
                  .filter((r) => (newTeacher.room_ids || []).includes(r.id))
                  .map((r) => <option key={r.id} value={r.id}>{r.name}</option>)
                }
              </select>
            </div>
          </div>

          <div className="flex gap-3 justify-end pt-2">
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
            const isEditing = editingId === teacher.id;

            if (isEditing) {
              return (
                <div key={teacher.id} className="japandi-card rounded-lg shadow-ambient p-5 card-appear">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
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
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
                    <div className="sm:col-span-2">
                      <label className="text-xs font-medium text-on-surface-variant mb-1.5 block">Classrooms</label>
                      <div className="flex flex-wrap gap-2 p-3 bg-surface-container rounded-lg border border-outline-variant/10 min-h-[46px]">
                        {rooms.length === 0 ? (
                          <span className="text-xs text-on-surface-variant">No classrooms available</span>
                        ) : (
                          rooms.map((r) => {
                            const isChecked = (editFields.room_ids || []).includes(r.id);
                            return (
                              <label key={r.id} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border cursor-pointer select-none transition-all ${isChecked ? 'bg-primary-container text-on-primary-container border-primary' : 'bg-surface-container-high text-on-surface-variant border-outline-variant/30 hover:border-outline-variant/60'}`}>
                                <input
                                  type="checkbox"
                                  checked={isChecked}
                                  onChange={(e) => {
                                    const updatedIds = e.target.checked
                                      ? [...(editFields.room_ids || []), r.id]
                                      : (editFields.room_ids || []).filter((id) => id !== r.id);
                                    let updatedPrimary = editFields.primary_room_id;
                                    if (!updatedIds.includes(updatedPrimary)) {
                                      updatedPrimary = updatedIds[0] || '';
                                    }
                                    setEditFields({ ...editFields, room_ids: updatedIds, primary_room_id: updatedPrimary });
                                  }}
                                  className="sr-only"
                                />
                                {r.name}
                              </label>
                            );
                          })
                        )}
                      </div>
                    </div>
                    <div>
                      <label className="text-xs font-medium text-on-surface-variant mb-1.5 block">Primary Classroom</label>
                      <select
                        value={editFields.primary_room_id}
                        onChange={(e) => setEditFields({ ...editFields, primary_room_id: e.target.value })}
                        disabled={!(editFields.room_ids && editFields.room_ids.length > 0)}
                        className={`${inputClass} disabled:opacity-50`}
                      >
                        <option value="">Select primary...</option>
                        {rooms
                          .filter((r) => (editFields.room_ids || []).includes(r.id))
                          .map((r) => <option key={r.id} value={r.id}>{r.name}</option>)
                        }
                      </select>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 pt-3">
                    <button
                      onClick={() => removeTeacher(teacher)}
                      className="flex items-center gap-1.5 text-xs text-error hover:text-on-error-container hover:bg-error-container/40 px-3 py-2 rounded transition-colors"
                      disabled={saving}
                      title="Remove this teacher"
                    >
                      <span className="material-symbols-outlined text-[18px]">person_remove</span>
                      Remove
                    </button>
                    <div className="ml-auto flex gap-2">
                      <button onClick={() => setEditingId(null)} className="btn-secondary !py-1.5 !px-4 text-xs" disabled={saving}>Cancel</button>
                      <button onClick={() => saveEdit(teacher.id)} className="btn-primary !py-1.5 !px-4 text-xs" disabled={saving}>Save</button>
                    </div>
                  </div>
                </div>
              );
            }

            const bootstrapUrl = bootstrapUrls[teacher.id];
            const issuing = issuingFor[teacher.id];

            return (
              <div key={teacher.id} className="japandi-card rounded-lg shadow-ambient p-5 group card-appear">
                {/* Top row: avatar + info + edit */}
                <div className="flex items-center gap-4">
                  <div className="w-11 h-11 rounded-full flex items-center justify-center text-sm font-semibold shrink-0 border border-outline-variant/15 bg-secondary-fixed text-on-secondary-fixed-variant">
                    {teacher.name.charAt(0).toUpperCase()}
                  </div>

                  <div className="flex-1 min-w-0">
                    <h4 className="font-semibold text-on-surface truncate">{teacher.name}</h4>
                    <div className="flex items-center gap-3 mt-0.5 text-xs text-on-surface-variant">
                      <span>{teacher.phone}</span>
                    </div>
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {teacher.room_ids && teacher.room_ids.length > 0 ? (
                        teacher.room_ids.map((rId) => {
                          const room = rooms.find((r) => r.id === rId);
                          if (!room) return null;
                          const isPrimary = teacher.room_id === rId;
                          return (
                            <span
                              key={rId}
                              className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium transition-all ${isPrimary ? 'bg-primary-container/85 text-on-primary-container border border-primary/20' : 'bg-surface-container-highest text-on-surface-variant border border-outline-variant/10'}`}
                            >
                              {room.name} {isPrimary && '(Primary)'}
                            </span>
                          );
                        })
                      ) : (
                        <span className="text-[10px] font-medium text-on-surface-variant/50 italic">Unassigned</span>
                      )}
                    </div>
                  </div>

                  <button
                    onClick={() => startEdit(teacher)}
                    className="opacity-0 group-hover:opacity-100 p-2 rounded-full hover:bg-surface-container-high text-outline transition-all"
                    title="Edit teacher"
                  >
                    <span className="material-symbols-outlined text-base">edit</span>
                  </button>
                </div>

                {/* Bootstrap URL panel */}
                <div className="mt-3 ml-[60px] p-3 bg-surface-container-low rounded-lg flex items-center gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-0.5">
                      Teacher app link
                    </p>
                    <span
                      className="text-xs font-mono text-on-surface block truncate"
                      title={bootstrapUrl || ''}
                    >
                      {issuing && !bootstrapUrl ? 'Generating…' : bootstrapUrl || 'Not yet generated'}
                    </span>
                  </div>
                  <button
                    onClick={() => copyTeacherUrl(bootstrapUrl)}
                    disabled={!bootstrapUrl || issuing}
                    className="btn-secondary !py-1 !px-3 text-xs shrink-0 disabled:opacity-40"
                  >
                    <span className="material-symbols-outlined text-sm mr-1">content_copy</span>
                    Copy
                  </button>
                  <button
                    onClick={() => window.open(bootstrapUrl, '_blank', 'noopener,noreferrer')}
                    disabled={!bootstrapUrl || issuing}
                    className="btn-secondary !py-1 !px-3 text-xs shrink-0 disabled:opacity-40"
                    title="Open the teacher portal in a new tab"
                  >
                    <span className="material-symbols-outlined text-sm mr-1">open_in_new</span>
                    Open
                  </button>
                  <button
                    onClick={() => regenerateTeacherUrl(teacher)}
                    disabled={issuing}
                    className="p-1.5 rounded-full hover:bg-surface-container-high text-outline shrink-0 disabled:opacity-40"
                    title="Regenerate (issues a fresh token)"
                  >
                    <span className="material-symbols-outlined text-sm">refresh</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

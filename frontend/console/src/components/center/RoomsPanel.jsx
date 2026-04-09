import { useState } from 'react';
import { createRoom, updateRoom, deleteRoom } from '../../api';

export default function RoomsPanel({ centerId, rooms, teachers, addToast, onRoomsChange }) {
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState('');
  const [newRoomName, setNewRoomName] = useState('');
  const [saving, setSaving] = useState(false);

  function startEdit(room) {
    setEditingId(room.id);
    setEditName(room.name);
  }

  async function saveEdit(roomId) {
    if (!editName.trim()) return;
    setSaving(true);
    try {
      await updateRoom(centerId, roomId, editName.trim());
      addToast('Room renamed');
      setEditingId(null);
      await onRoomsChange();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(roomId, roomName) {
    if (!confirm(`Delete "${roomName}"? Teachers and children in this room will be unassigned.`)) return;
    try {
      await deleteRoom(centerId, roomId);
      addToast('Room deleted', 'info');
      await onRoomsChange();
    } catch (err) {
      addToast(err.message, 'error');
    }
  }

  async function handleCreate(e) {
    e.preventDefault();
    if (!newRoomName.trim()) return;
    setSaving(true);
    try {
      await createRoom(centerId, newRoomName.trim());
      addToast('Room created');
      setNewRoomName('');
      await onRoomsChange();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      {rooms.map((room) => {
        const roomTeachers = teachers.filter((t) => t.room_id === room.id);
        const isEditing = editingId === room.id;

        return (
          <div key={room.id} className="japandi-card p-5 rounded-lg shadow-ambient border border-outline-variant/10 card-appear">
            <div className="flex items-center justify-between gap-4">
              {/* Room name */}
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <div className="w-10 h-10 rounded-full bg-secondary-container flex items-center justify-center shrink-0">
                  <span className="material-symbols-outlined text-on-secondary-container text-lg">meeting_room</span>
                </div>
                {isEditing ? (
                  <input
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') saveEdit(room.id);
                      if (e.key === 'Escape') setEditingId(null);
                    }}
                    autoFocus
                    className="flex-1 bg-surface-container-highest rounded px-3 py-1.5 text-on-surface outline-none focus:bg-surface-container-lowest border border-transparent focus:border-outline-variant/20 transition-colors"
                  />
                ) : (
                  <h3
                    className="font-headline text-lg text-on-surface cursor-pointer hover:text-primary transition-colors truncate"
                    onClick={() => startEdit(room)}
                    title="Click to rename"
                  >
                    {room.name}
                  </h3>
                )}
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 shrink-0">
                {isEditing ? (
                  <>
                    <button onClick={() => saveEdit(room.id)} disabled={saving} className="btn-primary !px-4 !py-1.5 text-xs">
                      Save
                    </button>
                    <button onClick={() => setEditingId(null)} className="btn-secondary !px-4 !py-1.5 text-xs">
                      Cancel
                    </button>
                  </>
                ) : (
                  <button
                    onClick={() => handleDelete(room.id, room.name)}
                    className="p-2 rounded-full hover:bg-error-container/40 text-outline hover:text-on-error-container transition-colors"
                    title="Delete room"
                  >
                    <span className="material-symbols-outlined text-lg">delete</span>
                  </button>
                )}
              </div>
            </div>

            {/* Teachers in this room */}
            {roomTeachers.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {roomTeachers.map((t) => (
                  <span key={t.id} className="inline-flex items-center gap-1.5 bg-surface-container-low px-3 py-1 rounded-full text-xs text-on-surface-variant font-medium">
                    <span className="material-symbols-outlined text-sm">person</span>
                    {t.name}
                  </span>
                ))}
              </div>
            )}
            {roomTeachers.length === 0 && !isEditing && (
              <p className="mt-2 text-xs text-on-surface-variant/60">No teachers assigned</p>
            )}
          </div>
        );
      })}

      {/* Add room form */}
      <form onSubmit={handleCreate} className="flex items-center gap-3 mt-6">
        <input
          type="text"
          value={newRoomName}
          onChange={(e) => setNewRoomName(e.target.value)}
          placeholder="New room name…"
          className="flex-1 bg-surface-container-highest rounded-full px-5 py-3 text-on-surface placeholder:text-outline outline-none focus:bg-surface-container-lowest border border-transparent focus:border-outline-variant/20 transition-colors"
        />
        <button type="submit" disabled={saving || !newRoomName.trim()} className="btn-primary !py-3 disabled:opacity-40">
          <span className="material-symbols-outlined text-base mr-1">add</span>
          Add Room
        </button>
      </form>

      {rooms.length === 0 && (
        <div className="text-center py-12 text-on-surface-variant">
          <span className="material-symbols-outlined text-4xl text-outline mb-3 block">meeting_room</span>
          <p className="font-medium">No rooms yet</p>
          <p className="text-sm mt-1">Create your first classroom above.</p>
        </div>
      )}
    </div>
  );
}

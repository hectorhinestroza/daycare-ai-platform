import { useState } from 'react';
import { createChild } from '../../api';

export default function AddChildModal({ centerId, rooms, addToast, onClose, onCreated }) {
  const [fields, setFields] = useState({
    name: '',
    dob: '',
    room_id: '',
    allergies: '',
    medical_notes: '',
  });
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!fields.name.trim()) return;
    setSaving(true);
    try {
      const data = { name: fields.name.trim() };
      if (fields.dob) data.dob = fields.dob;
      if (fields.room_id) data.room_id = fields.room_id;
      if (fields.allergies.trim()) data.allergies = fields.allergies.trim();
      if (fields.medical_notes.trim()) data.medical_notes = fields.medical_notes.trim();

      await createChild(centerId, data);
      addToast(`${data.name} enrolled`);
      onCreated();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSaving(false);
    }
  }

  const inputClass = 'w-full bg-surface-container-highest rounded px-4 py-3 text-on-surface placeholder:text-outline outline-none focus:bg-surface-container-lowest border border-transparent focus:border-outline-variant/20 transition-colors';

  return (
    <div className="fixed inset-0 bg-on-surface/30 backdrop-blur-sm z-[60] flex items-end sm:items-center justify-center" onClick={onClose}>
      <div className="glass-panel w-full max-w-lg rounded-t-lg sm:rounded-lg p-6 max-h-[85vh] overflow-y-auto modal-appear" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h3 className="font-headline text-2xl text-on-surface">Enroll Child</h3>
          <button onClick={onClose} className="p-2 rounded-full hover:bg-surface-container-high text-outline transition-colors">
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-xs font-medium text-on-surface-variant mb-1.5 block">Name *</label>
            <input
              type="text"
              value={fields.name}
              onChange={(e) => setFields({ ...fields, name: e.target.value })}
              placeholder="Full name"
              className={inputClass}
              autoFocus
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-on-surface-variant mb-1.5 block">Date of Birth</label>
              <input
                type="date"
                value={fields.dob}
                onChange={(e) => setFields({ ...fields, dob: e.target.value })}
                className={inputClass}
              />
            </div>
            <div>
              <label className="text-xs font-medium text-on-surface-variant mb-1.5 block">Classroom</label>
              <select
                value={fields.room_id}
                onChange={(e) => setFields({ ...fields, room_id: e.target.value })}
                className={inputClass}
              >
                <option value="">Unassigned</option>
                {rooms.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-on-surface-variant mb-1.5 block">Allergies</label>
            <input
              type="text"
              value={fields.allergies}
              onChange={(e) => setFields({ ...fields, allergies: e.target.value })}
              placeholder="None"
              className={inputClass}
            />
          </div>

          <div>
            <label className="text-xs font-medium text-on-surface-variant mb-1.5 block">Medical Notes</label>
            <textarea
              value={fields.medical_notes}
              onChange={(e) => setFields({ ...fields, medical_notes: e.target.value })}
              rows={2}
              placeholder="Any medical conditions or notes"
              className={`${inputClass} resize-none`}
            />
          </div>

          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={onClose} className="btn-secondary" disabled={saving}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={saving || !fields.name.trim()}>
              {saving ? 'Enrolling…' : 'Enroll Child'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

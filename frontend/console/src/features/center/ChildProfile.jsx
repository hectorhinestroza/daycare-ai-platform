import { useState, useEffect, useCallback } from 'react';
import { fetchChild, updateChild, addContact, deleteChild } from '../../api';
import ContactRow from './ContactRow';

const STATUSES = ['ENROLLED', 'ACTIVE', 'WAITLIST', 'UNENROLLED'];

export default function ChildProfile({ child, rooms, centerId, addToast, onUpdate }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [fields, setFields] = useState({});
  const [saving, setSaving] = useState(false);
  const [showAddContact, setShowAddContact] = useState(false);
  const [newContact, setNewContact] = useState({ name: '', phone: '', email: '', relationship_type: 'parent', can_pickup: true, is_primary: false });

  async function loadDetail() {
    try {
      const data = await fetchChild(centerId, child.id);
      setDetail(data);
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadDetail(); }, [centerId, child.id]);

  function startEdit() {
    setFields({
      name: detail.name || '',
      dob: detail.dob || '',
      room_id: detail.room_id || '',
      allergies: detail.allergies || '',
      medical_notes: detail.medical_notes || '',
      status: detail.status || 'ENROLLED',
    });
    setEditing(true);
  }

  async function saveEdit() {
    setSaving(true);
    try {
      const updates = {};
      if (fields.name && fields.name !== detail.name) updates.name = fields.name;
      if (fields.dob !== (detail.dob || '')) updates.dob = fields.dob || null;
      if (fields.room_id !== (detail.room_id || '')) updates.room_id = fields.room_id || null;
      if (fields.allergies !== (detail.allergies || '')) updates.allergies = fields.allergies || null;
      if (fields.medical_notes !== (detail.medical_notes || '')) updates.medical_notes = fields.medical_notes || null;
      if (fields.status !== detail.status) updates.status = fields.status;

      if (Object.keys(updates).length === 0) {
        setEditing(false);
        return;
      }
      await updateChild(centerId, child.id, updates);
      addToast('Child updated');
      setEditing(false);
      await loadDetail();
      onUpdate();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSaving(false);
    }
  }

  async function handleAddContact(e) {
    e.preventDefault();
    if (!newContact.name.trim()) return;
    setSaving(true);
    try {
      await addContact(centerId, child.id, newContact);
      addToast('Contact added');
      setShowAddContact(false);
      setNewContact({ name: '', phone: '', email: '', relationship_type: 'parent', can_pickup: true, is_primary: false });
      await loadDetail();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="spinner" />
      </div>
    );
  }

  if (!detail) return null;

  const inputClass = 'w-full bg-surface-container-highest rounded px-4 py-2.5 text-sm text-on-surface outline-none focus:bg-surface-container-lowest border border-transparent focus:border-outline-variant/20 transition-colors';

  return (
    <div className="px-5 pb-5 pt-3 space-y-6">
      {/* ── Child Info ── */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h4 className="font-headline text-lg text-on-surface">Profile</h4>
          {!editing && (
            <button onClick={startEdit} className="btn-secondary !py-1.5 !px-4 text-xs">
              <span className="material-symbols-outlined text-sm mr-1">edit</span>
              Edit
            </button>
          )}
        </div>

        {editing ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-on-surface-variant mb-1 block">Name</label>
              <input type="text" value={fields.name} onChange={(e) => setFields({ ...fields, name: e.target.value })} className={inputClass} />
            </div>
            <div>
              <label className="text-xs font-medium text-on-surface-variant mb-1 block">Date of Birth</label>
              <input type="date" value={fields.dob} onChange={(e) => setFields({ ...fields, dob: e.target.value })} className={inputClass} />
            </div>
            <div>
              <label className="text-xs font-medium text-on-surface-variant mb-1 block">Room</label>
              <select value={fields.room_id} onChange={(e) => setFields({ ...fields, room_id: e.target.value })} className={inputClass}>
                <option value="">Unassigned</option>
                {rooms.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-on-surface-variant mb-1 block">Status</label>
              <select value={fields.status} onChange={(e) => setFields({ ...fields, status: e.target.value })} className={inputClass}>
                {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="sm:col-span-2">
              <label className="text-xs font-medium text-on-surface-variant mb-1 block">Allergies</label>
              <input type="text" value={fields.allergies} onChange={(e) => setFields({ ...fields, allergies: e.target.value })} placeholder="None" className={inputClass} />
            </div>
            <div className="sm:col-span-2">
              <label className="text-xs font-medium text-on-surface-variant mb-1 block">Medical Notes</label>
              <textarea value={fields.medical_notes} onChange={(e) => setFields({ ...fields, medical_notes: e.target.value })} rows={2} placeholder="None" className={`${inputClass} resize-none`} />
            </div>
            <div className="sm:col-span-2 flex gap-3 justify-end pt-2">
              <button onClick={() => setEditing(false)} className="btn-secondary !py-2 !px-5 text-sm" disabled={saving}>Cancel</button>
              <button onClick={saveEdit} className="btn-primary !py-2 !px-5 text-sm" disabled={saving}>Save Changes</button>
            </div>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3 text-sm">
              <Field label="Date of Birth" value={detail.dob || '—'} />
              <div>
                <span className="text-xs text-on-surface-variant">Room</span>
                <div className="flex items-center gap-2 mt-0.5">
                  <p className="text-on-surface font-medium">
                    {rooms.find((r) => r.id === detail.room_id)?.name || 'Unassigned'}
                  </p>
                  {detail.room_id && (
                    <button 
                      onClick={async () => {
                        if (!confirm(`Remove ${detail.name} from this room?`)) return;
                        setSaving(true);
                        try {
                          await updateChild(centerId, child.id, { room_id: null });
                          addToast('Removed from room');
                          await loadDetail();
                          onUpdate();
                        } catch (err) {
                          addToast(err.message, 'error');
                        } finally {
                          setSaving(false);
                        }
                      }}
                      disabled={saving}
                      className="text-[10px] uppercase font-bold tracking-wider text-error opacity-70 hover:opacity-100 transition-opacity bg-error/10 px-2 py-0.5 rounded"
                      title="Remove from room"
                    >
                      Remove
                    </button>
                  )}
                </div>
              </div>
              <Field label="Status" value={detail.status} />
              <Field label="Enrolled" value={detail.enrollment_date || '—'} />
              <Field label="Allergies" value={detail.allergies || 'None'} full />
              <Field label="Medical Notes" value={detail.medical_notes || 'None'} full />
            </div>

            {/* Parent Portal Link */}
            <div className="mt-4 p-3 bg-surface-container-low rounded-lg flex items-center gap-3">
              <span className="material-symbols-outlined text-primary text-lg">link</span>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-on-surface-variant mb-0.5">Parent Portal Link</p>
                <p className="text-xs text-on-surface font-mono truncate">
                  {`${window.location.origin}/parent/${centerId}/${child.id}`}
                </p>
              </div>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(`${window.location.origin}/parent/${centerId}/${child.id}`);
                  addToast('Link copied!');
                }}
                className="btn-secondary !py-1.5 !px-3 text-xs shrink-0"
              >
                <span className="material-symbols-outlined text-sm">content_copy</span>
              </button>
            </div>
          </>
        )}
      </div>

      {/* ── Contacts ── */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h4 className="font-headline text-lg text-on-surface">
            Contacts
            <span className="ml-2 text-xs font-body font-medium text-on-surface-variant bg-surface-container px-2 py-0.5 rounded-full">
              {detail.parent_contacts?.length || 0}
            </span>
          </h4>
          {!showAddContact && (
            <button onClick={() => setShowAddContact(true)} className="btn-secondary !py-1.5 !px-4 text-xs">
              <span className="material-symbols-outlined text-sm mr-1">person_add</span>
              Add
            </button>
          )}
        </div>

        {detail.parent_contacts?.length > 0 ? (
          <div className="space-y-3">
            {detail.parent_contacts.map((c) => (
              <ContactRow key={c.id} contact={c} centerId={centerId} addToast={addToast} onUpdate={loadDetail} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-on-surface-variant/60 py-2">No contacts added yet.</p>
        )}

        {/* Add contact form */}
        {showAddContact && (
          <form onSubmit={handleAddContact} className="mt-4 bg-surface-container-low rounded-lg p-4 space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-on-surface-variant mb-1 block">Name</label>
                <input type="text" value={newContact.name} onChange={(e) => setNewContact({ ...newContact, name: e.target.value })} className={inputClass} required />
              </div>
              <div>
                <label className="text-xs font-medium text-on-surface-variant mb-1 block">Relationship</label>
                <select value={newContact.relationship_type} onChange={(e) => setNewContact({ ...newContact, relationship_type: e.target.value })} className={inputClass}>
                  <option value="parent">Parent</option>
                  <option value="guardian">Guardian</option>
                  <option value="emergency">Emergency</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-on-surface-variant mb-1 block">Phone</label>
                <input type="tel" value={newContact.phone} onChange={(e) => setNewContact({ ...newContact, phone: e.target.value })} placeholder="+1 555-0100" className={inputClass} />
              </div>
              <div>
                <label className="text-xs font-medium text-on-surface-variant mb-1 block">Email</label>
                <input type="email" value={newContact.email} onChange={(e) => setNewContact({ ...newContact, email: e.target.value })} placeholder="parent@email.com" className={inputClass} />
              </div>
            </div>
            <div className="flex items-center gap-4 text-sm">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={newContact.can_pickup} onChange={(e) => setNewContact({ ...newContact, can_pickup: e.target.checked })} className="accent-primary" />
                <span className="text-on-surface-variant">Can pick up</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={newContact.is_primary} onChange={(e) => setNewContact({ ...newContact, is_primary: e.target.checked })} className="accent-primary" />
                <span className="text-on-surface-variant">Primary contact</span>
              </label>
            </div>
            <div className="flex gap-3 justify-end pt-1">
              <button type="button" onClick={() => setShowAddContact(false)} className="btn-secondary !py-2 !px-4 text-xs" disabled={saving}>Cancel</button>
              <button type="submit" className="btn-primary !py-2 !px-4 text-xs" disabled={saving || !newContact.name.trim()}>Add Contact</button>
            </div>
          </form>
        )}
      </div>

      {/* ── Danger Zone ── */}
      <div className="pt-6 mt-6 border-t border-error/20 flex justify-end">
        <button
          onClick={async () => {
            if (!confirm(`Are you completely sure you want to permanently delete ${child.name}? This cannot be undone.`)) return;
            setSaving(true);
            try {
              await deleteChild(centerId, child.id);
              addToast('Child deleted permanently', 'info');
              onUpdate();
            } catch (err) {
              addToast(err.message, 'error');
              setSaving(false);
            }
          }}
          disabled={saving}
          className="flex items-center gap-1.5 text-xs text-error hover:text-on-error-container hover:bg-error-container/40 px-3 py-2 rounded transition-colors"
        >
          <span className="material-symbols-outlined text-[18px]">delete_forever</span>
          Delete Child
        </button>
      </div>
    </div>
  );
}

function Field({ label, value, full }) {
  return (
    <div className={full ? 'sm:col-span-2' : ''}>
      <span className="text-xs text-on-surface-variant">{label}</span>
      <p className="text-on-surface font-medium mt-0.5">{value}</p>
    </div>
  );
}

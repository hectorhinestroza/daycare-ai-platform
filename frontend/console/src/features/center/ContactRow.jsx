import { useEffect, useState } from 'react';
import { issueParentToken, updateContact } from '../../api';

const REL_STYLE = {
  parent:    'bg-primary-fixed text-on-primary-container',
  guardian:  'bg-secondary-fixed text-on-secondary-fixed-variant',
  emergency: 'bg-error-container text-on-error-container',
};

export default function ContactRow({ contact, centerId, addToast, onUpdate }) {
  const [editing, setEditing] = useState(false);
  const [fields, setFields] = useState({});
  const [saving, setSaving] = useState(false);
  const [issuing, setIssuing] = useState(false);
  const [bootstrapUrl, setBootstrapUrl] = useState(null);

  const canIssue = contact.relationship_type === 'parent' || contact.relationship_type === 'guardian';

  // Auto-mint a bootstrap URL on first render for parent/guardian contacts.
  // The URL is then visible by default in the row's panel — no extra click
  // needed to see it. The director still has to click Copy to put it in the
  // clipboard (sync write, iOS Safari requires this).
  useEffect(() => {
    if (!canIssue) return;
    let cancelled = false;
    setIssuing(true);
    issueParentToken({
      centerId,
      parentContactId: contact.id,
      childIds: [contact.child_id],
    })
      .then((result) => {
        if (!cancelled) setBootstrapUrl(result.bootstrap_url);
      })
      .catch((err) => {
        if (!cancelled) addToast(err.message || 'Failed to mint link', 'error');
      })
      .finally(() => {
        if (!cancelled) setIssuing(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contact.id, contact.child_id, canIssue, centerId]);

  // Force a fresh token (e.g., after revoking the old one).
  async function regenerateUrl() {
    setIssuing(true);
    setBootstrapUrl(null);
    try {
      const result = await issueParentToken({
        centerId,
        parentContactId: contact.id,
        childIds: [contact.child_id],
      });
      setBootstrapUrl(result.bootstrap_url);
    } catch (err) {
      addToast(err.message || 'Failed to mint link', 'error');
    } finally {
      setIssuing(false);
    }
  }

  function copyToClipboard() {
    // Sync — fired directly from the click handler, no await before write.
    navigator.clipboard.writeText(bootstrapUrl).then(
      () => addToast('Copied!'),
      () => addToast('Copy blocked — long-press the URL to copy manually', 'error'),
    );
  }

  function startEdit() {
    setFields({
      name: contact.name,
      phone: contact.phone || '',
      email: contact.email || '',
      relationship_type: contact.relationship_type,
      can_pickup: contact.can_pickup,
      is_primary: contact.is_primary,
    });
    setEditing(true);
  }

  async function save() {
    setSaving(true);
    try {
      const updates = {};
      if (fields.name !== contact.name) updates.name = fields.name;
      if (fields.phone !== (contact.phone || '')) updates.phone = fields.phone || null;
      if (fields.email !== (contact.email || '')) updates.email = fields.email || null;
      if (fields.relationship_type !== contact.relationship_type) updates.relationship_type = fields.relationship_type;
      if (fields.can_pickup !== contact.can_pickup) updates.can_pickup = fields.can_pickup;
      if (fields.is_primary !== contact.is_primary) updates.is_primary = fields.is_primary;

      if (Object.keys(updates).length === 0) { setEditing(false); return; }
      await updateContact(centerId, contact.id, updates);
      addToast('Contact updated');
      setEditing(false);
      onUpdate();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSaving(false);
    }
  }

  const relStyle = REL_STYLE[contact.relationship_type] || REL_STYLE.parent;
  const inputClass = 'w-full bg-surface-container-highest rounded px-3 py-1.5 text-sm text-on-surface outline-none focus:bg-surface-container-lowest border border-transparent focus:border-outline-variant/20 transition-colors';

  if (editing) {
    return (
      <div className="bg-surface-container-low rounded-lg p-4 space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <input type="text" value={fields.name} onChange={(e) => setFields({ ...fields, name: e.target.value })} placeholder="Name" className={inputClass} />
          <select value={fields.relationship_type} onChange={(e) => setFields({ ...fields, relationship_type: e.target.value })} className={inputClass}>
            <option value="parent">Parent</option>
            <option value="guardian">Guardian</option>
            <option value="emergency">Emergency</option>
          </select>
          <input type="tel" value={fields.phone} onChange={(e) => setFields({ ...fields, phone: e.target.value })} placeholder="Phone" className={inputClass} />
          <input type="email" value={fields.email} onChange={(e) => setFields({ ...fields, email: e.target.value })} placeholder="Email" className={inputClass} />
        </div>
        <div className="flex items-center gap-4 text-sm">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={fields.can_pickup} onChange={(e) => setFields({ ...fields, can_pickup: e.target.checked })} className="accent-primary" />
            <span className="text-on-surface-variant">Can pick up</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={fields.is_primary} onChange={(e) => setFields({ ...fields, is_primary: e.target.checked })} className="accent-primary" />
            <span className="text-on-surface-variant">Primary</span>
          </label>
          <div className="ml-auto flex gap-2">
            <button onClick={() => setEditing(false)} className="btn-secondary !py-1 !px-3 text-xs" disabled={saving}>Cancel</button>
            <button onClick={save} className="btn-primary !py-1 !px-3 text-xs" disabled={saving}>Save</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="py-2 group">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-surface-container flex items-center justify-center shrink-0">
          <span className="material-symbols-outlined text-on-surface-variant text-base">person</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-on-surface truncate">{contact.name}</span>
            <span className={`text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${relStyle}`}>
              {contact.relationship_type}
            </span>
            {contact.is_primary && (
              <span className="text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-secondary text-white">Primary</span>
            )}
            {contact.can_pickup && (
              <span className="material-symbols-outlined text-secondary text-sm" title="Can pick up" style={{ fontVariationSettings: "'FILL' 1" }}>verified_user</span>
            )}
          </div>
          <div className="flex items-center gap-3 mt-0.5 text-xs text-on-surface-variant">
            {contact.phone && <span>{contact.phone}</span>}
            {contact.email && <span>{contact.email}</span>}
          </div>
        </div>
        <button
          onClick={startEdit}
          className="opacity-0 group-hover:opacity-100 p-1.5 rounded-full hover:bg-surface-container-high text-outline transition-all"
          title="Edit contact"
        >
          <span className="material-symbols-outlined text-base">edit</span>
        </button>
      </div>

      {/* Bootstrap URL panel — auto-shown for parent/guardian contacts.
          Mint happens on mount; Copy fires sync from a fresh user gesture. */}
      {canIssue && (
        <div className="mt-2 ml-11 p-3 bg-surface-container-low rounded-lg flex items-center gap-2">
          <div className="flex-1 min-w-0">
            <p className="text-[10px] uppercase tracking-wider text-on-surface-variant mb-0.5">
              Parent portal link
            </p>
            <span
              className="text-xs font-mono text-on-surface block truncate"
              title={bootstrapUrl || ''}
            >
              {issuing && !bootstrapUrl ? 'Generating…' : bootstrapUrl || 'Not yet generated'}
            </span>
          </div>
          <button
            onClick={copyToClipboard}
            disabled={!bootstrapUrl || issuing}
            className="btn-secondary !py-1 !px-3 text-xs shrink-0 disabled:opacity-40"
          >
            <span className="material-symbols-outlined text-sm mr-1">content_copy</span>
            Copy
          </button>
          <button
            onClick={regenerateUrl}
            disabled={issuing}
            className="p-1.5 rounded-full hover:bg-surface-container-high text-outline shrink-0 disabled:opacity-40"
            title="Regenerate (issues a fresh token)"
          >
            <span className="material-symbols-outlined text-sm">refresh</span>
          </button>
        </div>
      )}
    </div>
  );
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function fetchTeacherQueue(centerId) {
  const res = await fetch(`${API_BASE}/api/events/pending/teacher/${centerId}`);
  if (!res.ok) throw new Error(`Failed to fetch teacher queue: ${res.status}`);
  return res.json();
}

export async function fetchDirectorQueue(centerId) {
  const res = await fetch(`${API_BASE}/api/events/pending/director/${centerId}`);
  if (!res.ok) throw new Error(`Failed to fetch director queue: ${res.status}`);
  return res.json();
}

export async function approveEvent(centerId, eventId) {
  const res = await fetch(`${API_BASE}/api/events/${centerId}/${eventId}/approve`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Failed to approve: ${res.status}`);
  return res.json();
}

export async function rejectEvent(centerId, eventId) {
  const res = await fetch(`${API_BASE}/api/events/${centerId}/${eventId}/reject`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Failed to reject: ${res.status}`);
  return res.json();
}

export async function editEvent(centerId, eventId, updates) {
  const res = await fetch(`${API_BASE}/api/events/${centerId}/${eventId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  if (!res.ok) throw new Error(`Failed to edit: ${res.status}`);
  return res.json();
}

export async function batchApprove(centerId, childName) {
  const res = await fetch(`${API_BASE}/api/events/${centerId}/batch-approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ child_name: childName }),
  });
  if (!res.ok) throw new Error(`Failed to batch approve: ${res.status}`);
  return res.json();
}

export async function fetchHistory(centerId, { status, limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  const res = await fetch(`${API_BASE}/api/events/history/${centerId}?${params}`);
  if (!res.ok) throw new Error(`Failed to fetch history: ${res.status}`);
  return res.json();
}

export async function fetchActivityLog(centerId, { action, eventId, limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (action) params.set('action', action);
  if (eventId) params.set('event_id', eventId);
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  const res = await fetch(`${API_BASE}/api/activity/${centerId}?${params}`);
  if (!res.ok) throw new Error(`Failed to fetch activity log: ${res.status}`);
  return res.json();
}

// ─── Narratives ─────────────────────────────────────────────

export async function fetchNarrative(centerId, childId, targetDate) {
  const res = await fetch(`${API_BASE}/api/narratives/${centerId}/${childId}/${targetDate}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Failed to fetch narrative: ${res.status}`);
  return res.json();
}

export async function generateNarrative(centerId, childId, targetDate) {
  const params = targetDate ? `?target_date=${targetDate}` : '';
  const res = await fetch(`${API_BASE}/api/narratives/${centerId}/${childId}/generate${params}`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Failed to generate narrative: ${res.status}`);
  return res.json();
}

export async function generateAllNarratives(centerId, targetDate) {
  const params = targetDate ? `?target_date=${targetDate}` : '';
  const res = await fetch(`${API_BASE}/api/narratives/${centerId}/generate-all${params}`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Failed to generate narratives: ${res.status}`);
  return res.json();
}

// ─── Parent Feed ────────────────────────────────────────────

export async function fetchParentFeed(centerId, childId, { limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams();
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  const res = await fetch(`${API_BASE}/api/events/feed/${centerId}/${childId}?${params}`);
  if (!res.ok) throw new Error(`Failed to fetch feed: ${res.status}`);
  return res.json();
}

export async function fetchChildPublic(centerId, childId) {
  const res = await fetch(`${API_BASE}/api/children/${centerId}/${childId}`);
  if (!res.ok) throw new Error(`Failed to fetch child: ${res.status}`);
  return res.json();
}

// ─── Onboarding: Rooms ──────────────────────────────────────

export async function fetchRooms(centerId) {
  const res = await fetch(`${API_BASE}/api/rooms/${centerId}`);
  if (!res.ok) throw new Error(`Failed to fetch rooms: ${res.status}`);
  return res.json();
}

export async function createRoom(centerId, name) {
  const res = await fetch(`${API_BASE}/api/rooms/${centerId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(`Failed to create room: ${res.status}`);
  return res.json();
}

export async function updateRoom(centerId, roomId, name) {
  const res = await fetch(`${API_BASE}/api/rooms/${centerId}/${roomId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(`Failed to update room: ${res.status}`);
  return res.json();
}

export async function deleteRoom(centerId, roomId) {
  const res = await fetch(`${API_BASE}/api/rooms/${centerId}/${roomId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`Failed to delete room: ${res.status}`);
}

// ─── Onboarding: Teachers ───────────────────────────────────

export async function fetchTeachers(centerId) {
  const res = await fetch(`${API_BASE}/api/teachers/${centerId}`);
  if (!res.ok) throw new Error(`Failed to fetch teachers: ${res.status}`);
  return res.json();
}

export async function createTeacher(centerId, data) {
  const res = await fetch(`${API_BASE}/api/teachers/${centerId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to create teacher: ${res.status}`);
  return res.json();
}

export async function updateTeacher(centerId, teacherId, updates) {
  const res = await fetch(`${API_BASE}/api/teachers/${centerId}/${teacherId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  if (!res.ok) throw new Error(`Failed to update teacher: ${res.status}`);
  return res.json();
}

// ─── Onboarding: Children ───────────────────────────────────

export async function fetchChildren(centerId, { room_id, status } = {}) {
  const params = new URLSearchParams();
  if (room_id) params.set('room_id', room_id);
  if (status) params.set('status', status);
  const qs = params.toString();
  const res = await fetch(`${API_BASE}/api/children/${centerId}${qs ? `?${qs}` : ''}`);
  if (!res.ok) throw new Error(`Failed to fetch children: ${res.status}`);
  return res.json();
}

export async function fetchChild(centerId, childId) {
  const res = await fetch(`${API_BASE}/api/children/${centerId}/${childId}`);
  if (!res.ok) throw new Error(`Failed to fetch child: ${res.status}`);
  return res.json();
}

export async function createChild(centerId, data) {
  const res = await fetch(`${API_BASE}/api/children/${centerId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to enroll child: ${res.status}`);
  return res.json();
}

export async function updateChild(centerId, childId, updates) {
  const res = await fetch(`${API_BASE}/api/children/${centerId}/${childId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  if (!res.ok) throw new Error(`Failed to update child: ${res.status}`);
  return res.json();
}

export async function deleteChild(centerId, childId) {
  const res = await fetch(`${API_BASE}/api/children/${centerId}/${childId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`Failed to delete child: ${res.status}`);
  return res.status === 204;
}

// ─── Onboarding: Parent Contacts ───────────────────────────────────

export async function addContact(centerId, childId, data) {
  const res = await fetch(`${API_BASE}/api/children/${centerId}/${childId}/contacts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to add contact: ${res.status}`);
  return res.json();
}

export async function updateContact(centerId, contactId, updates) {
  const res = await fetch(`${API_BASE}/api/contacts/${centerId}/${contactId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  if (!res.ok) throw new Error(`Failed to update contact: ${res.status}`);
  return res.json();
}

// ─── Consent ───────────────────────────────────

export async function fetchConsentDetails(token) {
  const res = await fetch(`${API_BASE}/api/consent/${token}`);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Failed to fetch consent details: ${res.status}`);
  }
  return res.json();
}

export async function submitConsent(token, data) {
  const res = await fetch(`${API_BASE}/api/consent/${token}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Failed to submit consent: ${res.status}`);
  }
  return res.json();
}

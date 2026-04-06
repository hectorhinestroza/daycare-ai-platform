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

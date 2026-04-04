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

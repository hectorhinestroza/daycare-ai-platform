import React, { useState, useEffect } from 'react';
import { fetchActivityLog } from '../api';
import EmptyState from './EmptyState';

function getActionStyle(action) {
  switch (action) {
    case 'APPROVE':
    case 'BATCH_APPROVE':
      return 'bg-green-100 text-green-800 border-green-200';
    case 'REJECT':
      return 'bg-red-100 text-red-800 border-red-200';
    case 'EDIT':
      return 'bg-yellow-100 text-yellow-800 border-yellow-200';
    case 'CREATE':
      return 'bg-blue-100 text-blue-800 border-blue-200';
    default:
      return 'bg-gray-100 text-gray-800 border-gray-200';
  }
}

export default function ActivityLog({ centerId }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function loadLogs() {
      try {
        setLoading(true);
        const data = await fetchActivityLog(centerId);
        setLogs(data);
        setError(null);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    if (centerId) {
      loadLogs();
    }
  }, [centerId]);

  if (loading) {
    return <div className="p-4 text-center text-gray-500">Loading activity log...</div>;
  }

  if (error) {
    return <div className="p-4 text-center text-red-600">Error: {error}</div>;
  }

  if (logs.length === 0) {
    return (
      <div className="mt-8">
        <EmptyState role="history" />
      </div>
    );
  }

  return (
    <div className="space-y-4 px-4 pb-20">
      {logs.map((log) => (
        <div key={log.id} className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
          <div className="flex justify-between items-start mb-2">
            <span className={`px-2 py-1 text-xs font-semibold rounded-full border ${getActionStyle(log.action)}`}>
              {log.action}
            </span>
            <span className="text-xs text-gray-400">
              {new Date(log.created_at).toLocaleString([], {
                month: 'short',
                day: 'numeric',
                hour: 'numeric',
                minute: '2-digit',
              })}
            </span>
          </div>

          <div className="text-sm text-gray-700 space-y-1">
            {log.details && log.details.child_name && (
              <p>
                <span className="font-medium text-gray-900">Child:</span> {log.details.child_name}
              </p>
            )}
            
            {log.details && log.details.event_type && (
              <p>
                <span className="font-medium text-gray-900">Event:</span> {log.details.event_type}
              </p>
            )}

            {log.action === 'BATCH_APPROVE' && log.details && (
              <p>
                <span className="font-medium text-gray-900">Count:</span> {log.details.count} events approved.
              </p>
            )}

            {log.action === 'EDIT' && log.details && log.details.changes && (
              <div className="mt-2 bg-gray-50 rounded p-2 text-xs font-mono">
                {Object.entries(log.details.changes).map(([field, change]) => (
                  <div key={field} className="mb-1 last:mb-0">
                    <span className="text-gray-500">{field}:</span>{' '}
                    <span className="line-through text-red-500 mr-1">{change.old}</span>
                    <span className="text-green-600">{change.new}</span>
                  </div>
                ))}
              </div>
            )}
            
            {!['APPROVE', 'REJECT', 'EDIT', 'BATCH_APPROVE'].includes(log.action) && log.details && (
              <pre className="text-xs text-gray-500 bg-gray-50 p-2 rounded mt-2 overflow-x-auto">
                {JSON.stringify(log.details, null, 2)}
              </pre>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

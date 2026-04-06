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

function getActivityMessage(log) {
  const { action, details } = log;
  const child = details?.child_name || 'an unknown child';
  const event = details?.event_type || 'event';
  
  switch(action) {
    case 'APPROVE':
      return <span>Approved <strong>{event}</strong> event for <strong>{child}</strong>.</span>;
    case 'REJECT':
      return <span>Rejected <strong>{event}</strong> event for <strong>{child}</strong>.</span>;
    case 'BATCH_APPROVE':
      return <span>Batch approved <strong>{details?.count || 'multiple'}</strong> events for <strong>{child}</strong>.</span>;
    case 'EDIT':
      return <span>Edited <strong>{event}</strong> event for <strong>{child}</strong>.</span>;
    default:
      return <span>Performed {action} on {child}.</span>;
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

  const grouped = logs.reduce((acc, log) => {
    const teacherName = log.teacher_name || 'System';
    if (!acc[teacherName]) acc[teacherName] = [];
    acc[teacherName].push(log);
    return acc;
  }, {});

  return (
    <div className="event-groups">
      {Object.entries(grouped).map(([teacherName, teacherLogs]) => (
        <section key={teacherName} className="child-group mb-8">
          <h2 className="group-header">
            <span className="child-avatar">
              {teacherName.charAt(0).toUpperCase()}
            </span>
            {teacherName}
            <span className="group-count">{teacherLogs.length}</span>
          </h2>
          <div className="space-y-4">
            {teacherLogs.map((log) => (
              <div key={log.id} className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
                <div className="flex justify-between items-center mb-3">
                  <span className={`px-2 py-0.5 text-[10px] uppercase font-bold tracking-wider rounded-full border ${getActionStyle(log.action)}`}>
                    {log.action.replace('_', ' ')}
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

                <div className="text-sm text-gray-700">
                  <p>{getActivityMessage(log)}</p>

                  {log.action === 'EDIT' && log.details && log.details.changes && (
                    <div className="mt-3 bg-gray-50 border border-gray-100 rounded-lg p-3 text-xs font-mono space-y-2">
                      {Object.entries(log.details.changes).map(([field, change]) => (
                        <div key={field} className="flex flex-col">
                          <span className="text-gray-400 capitalize mb-1">{field.replace('_', ' ')}:</span>
                          <div className="flex items-center space-x-2">
                            <span className="line-through text-red-400 truncate max-w-[45%]">
                              {String(change.old)}
                            </span>
                            <span className="text-gray-300">→</span>
                            <span className="text-green-600 font-medium truncate max-w-[45%]">
                              {String(change.new)}
                            </span>
                          </div>
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
        </section>
      ))}
    </div>
  );
}

export default function EmptyState({ role }) {
  const config = {
    director: { icon: '🎯', title: 'All caught up!', desc: 'No flagged events need your attention right now.' },
    teacher: { icon: '✨', title: 'All caught up!', desc: 'No events are waiting for your review.' },
    history: { icon: '📭', title: 'No history yet', desc: 'Approved and rejected events will appear here.' },
  };
  const { icon, title, desc } = config[role] || config.teacher;

  return (
    <div className="empty-state">
      <div className="empty-icon">{icon}</div>
      <h2>{title}</h2>
      <p>{desc}</p>
    </div>
  );
}

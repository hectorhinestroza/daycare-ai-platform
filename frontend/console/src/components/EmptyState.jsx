export default function EmptyState({ role }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        {role === 'director' ? '🎯' : '✨'}
      </div>
      <h2>All caught up!</h2>
      <p>
        {role === 'director'
          ? 'No flagged events need your attention right now.'
          : 'No events are waiting for your review.'}
      </p>
    </div>
  );
}

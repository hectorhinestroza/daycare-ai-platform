const CONFIG = {
  director: {
    icon: 'task_alt',
    title: 'All caught up!',
    desc: 'No flagged events need your attention right now.',
  },
  teacher: {
    icon: 'auto_awesome',
    title: 'All caught up!',
    desc: 'No events are waiting for your review.',
  },
  history: {
    icon: 'inbox',
    title: 'No history yet',
    desc: 'Approved and rejected events will appear here.',
  },
};

export default function EmptyState({ role }) {
  const { icon, title, desc } = CONFIG[role] || CONFIG.teacher;

  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <div className="w-16 h-16 rounded-full bg-surface-container-low flex items-center justify-center mb-6">
        <span className="material-symbols-outlined text-3xl text-outline">{icon}</span>
      </div>
      <h2 className="font-headline text-2xl text-on-surface mb-2">{title}</h2>
      <p className="text-on-surface-variant max-w-xs leading-relaxed">{desc}</p>
    </div>
  );
}

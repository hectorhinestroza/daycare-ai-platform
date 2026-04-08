import { useState, useEffect } from 'react';

const TOAST_CONFIG = {
  success: { icon: 'check_circle', barClass: 'bg-secondary' },
  error:   { icon: 'error',        barClass: 'bg-error' },
  info:    { icon: 'info',         barClass: 'bg-tertiary' },
};

export default function Toast({ message, type = 'success', onClose }) {
  const [visible, setVisible] = useState(true);
  const config = TOAST_CONFIG[type] || TOAST_CONFIG.info;

  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false);
      setTimeout(onClose, 300);
    }, 3000);
    return () => clearTimeout(timer);
  }, [onClose]);

  return (
    <div
      className={`flex items-center gap-3 bg-surface-container-lowest rounded-lg shadow-ambient px-4 py-3 min-w-[240px] max-w-[360px] border border-outline-variant/15 relative overflow-hidden ${
        visible ? 'toast-enter' : 'toast-exit'
      }`}
    >
      {/* Left accent */}
      <div className={`absolute left-0 top-0 w-1 h-full ${config.barClass}`} />
      <span className="material-symbols-outlined text-on-surface-variant text-lg ml-2" style={{ fontVariationSettings: "'FILL' 1" }}>
        {config.icon}
      </span>
      <span className="flex-1 text-sm text-on-surface font-medium">{message}</span>
      <button
        onClick={() => { setVisible(false); onClose(); }}
        className="text-outline hover:text-on-surface transition-colors"
      >
        <span className="material-symbols-outlined text-base">close</span>
      </button>
    </div>
  );
}

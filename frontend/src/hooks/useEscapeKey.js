import { useEffect } from 'react';

/** Calls onClose when Escape is pressed, while active is truthy. */
export function useEscapeKey(onClose, active) {
  useEffect(() => {
    if (!active) return;
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [active, onClose]);
}

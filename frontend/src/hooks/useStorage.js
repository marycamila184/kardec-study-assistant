import { useState, useEffect } from 'react';

export function useStorage(key, defaultValue) {
  const [value, setValue] = useState(() => {
    try {
      const stored = localStorage.getItem(key);
      return stored !== null ? JSON.parse(stored) : defaultValue;
    } catch { return defaultValue; }
  });

  const setStored = (next) => {
    const val = typeof next === 'function' ? next(value) : next;
    setValue(val);
    try { localStorage.setItem(key, JSON.stringify(val)); } catch {}
  };

  return [value, setStored];
}

import { useState, useEffect } from 'react';
import { lightTheme, darkTheme } from '../constants/theme';

export function useTheme() {
  const [darkMode, setDarkMode] = useState(() => {
    try { return localStorage.getItem('dialogando_dark') === 'true'; } catch { return false; }
  });

  useEffect(() => {
    try { localStorage.setItem('dialogando_dark', String(darkMode)); } catch {}
  }, [darkMode]);

  const toggleDark = () => setDarkMode(d => !d);
  const theme = darkMode ? darkTheme : lightTheme;

  return { darkMode, toggleDark, theme };
}

import { useEffect, useRef } from 'react';

export function useReminder({ enabled, time, permission, onNotificationClick }) {
  // Keep the latest callback in a ref so the interval-holding effect below
  // doesn't need onNotificationClick in its dependency array — the caller
  // (App.jsx) can pass a fresh function identity on every render without
  // tearing down and rebuilding the 30s interval each time.
  const onClickRef = useRef(onNotificationClick);
  useEffect(() => {
    onClickRef.current = onNotificationClick;
  }, [onNotificationClick]);

  useEffect(() => {
    if (!enabled || permission !== 'granted') return;
    let lastMinuteFired = null;

    const interval = setInterval(() => {
      const now = new Date();
      const [h, m] = time.split(':').map(Number);
      if (now.getHours() === h && now.getMinutes() === m && lastMinuteFired !== m) {
        lastMinuteFired = m;
        const notification = new Notification('Dialogando com a Doutrina 📖', {
          body: 'É hora do seu estudo diário! Que tal começar com o trecho de hoje?',
        });
        notification.onclick = () => {
          window.focus();
          onClickRef.current?.();
          notification.close();
        };
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [enabled, time, permission]);
}

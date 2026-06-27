import { useEffect } from 'react';

export function useReminder({ enabled, time, permission }) {
  useEffect(() => {
    if (!enabled || permission !== 'granted') return;
    let lastMinuteFired = null;

    const interval = setInterval(() => {
      const now = new Date();
      const [h, m] = time.split(':').map(Number);
      if (now.getHours() === h && now.getMinutes() === m && lastMinuteFired !== m) {
        lastMinuteFired = m;
        new Notification('Dialogando com a Doutrina 📖', {
          body: 'É hora do seu estudo diário! Que tal começar com o trecho de hoje?',
        });
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [enabled, time, permission]);
}

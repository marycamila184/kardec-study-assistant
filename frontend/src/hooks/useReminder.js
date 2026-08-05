import { useEffect, useRef } from 'react';

/**
 * ⚠️ NOT CALLED. The study reminder is switched off for production as of
 * 2026-08-05 — disconnected, not deleted, like Refletir. App.jsx's import and
 * call are commented out, as is the Settings section that configured it. See
 * docs/superpowers/specs/2026-08-05-desligar-lembrete-design.md
 *
 * The hook is correct for what it is. What it is, is the problem: a 30-second
 * interval living in the page, which can only fire while the tab is open and
 * in the foreground. Backgrounding a mobile browser or locking the screen
 * freezes it, and on iOS Safari outside a Home Screen app `Notification` is
 * undefined entirely. So a reminder set for 08:00 arrived only for a reader
 * already looking at the app at 08:00 — who did not need reminding.
 *
 * Do not "fix" this by shortening the interval or moving it to a worker: a web
 * page cannot schedule a notification for a time when it is not running. The
 * API that would have allowed it (`TimestampTrigger`) never shipped past an
 * origin trial. Delivery with the app closed requires Web Push — a service
 * worker, VAPID keys, subscriptions stored server-side and a scheduler. That
 * last part is why this is a design decision and not a rewrite of this file:
 * a stored push subscription is a durable per-device identifier, which is the
 * one thing this backend has been careful never to hold.
 */
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

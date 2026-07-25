import { useEffect, useRef } from 'react';

/**
 * Keeps a scroll container pinned to the bottom as its content grows — e.g.
 * while the typewriter reveals a long answer one word at a time. A one-shot
 * scroll fires before that text exists, so without this the viewport falls
 * behind and the user has to scroll manually.
 *
 * The pin is polite: it only follows growth while the user is already near
 * the bottom. If they scroll up (to re-read an earlier part mid-reveal) we
 * stop yanking them down, and resume once they scroll back to the bottom.
 *
 *   ref — ref to the scrollable element
 *   options.threshold — px from the bottom still considered "at the bottom"
 */
export function useStickToBottom(ref, { threshold = 80 } = {}) {
  const pinnedRef = useRef(true);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const nearBottom = () =>
      el.scrollHeight - el.scrollTop - el.clientHeight <= threshold;

    const onScroll = () => { pinnedRef.current = nearBottom(); };
    el.addEventListener('scroll', onScroll, { passive: true });

    const observer = new MutationObserver(() => {
      if (pinnedRef.current) el.scrollTop = el.scrollHeight;
    });
    observer.observe(el, { childList: true, subtree: true, characterData: true });

    return () => {
      el.removeEventListener('scroll', onScroll);
      observer.disconnect();
    };
  }, [ref, threshold]);
}

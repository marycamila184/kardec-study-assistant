import { useCallback, useEffect, useRef, useState } from 'react';

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
 * Returns a **callback ref**, which must be the one placed on the scrollable
 * element. That is the whole point of this hook's shape. It used to read
 * `ref.current` inside an effect whose dependencies were `[ref, threshold]` —
 * a ref object has a stable identity and the threshold is a constant, so the
 * effect ran exactly once, on mount, and if the container was not in the DOM at
 * that instant it returned early and never got another chance. Every consumer
 * renders its container conditionally (App behind `!isHome`, ExplorarObras
 * behind `hasMessages`), so the observer was silently never installed and the
 * viewport stopped following the reveal. React calls a callback ref with the
 * node when it mounts and with null when it unmounts, which is exactly the
 * signal a ref object cannot give.
 *
 *   ref — optional ref object to populate too, for callers that also scroll
 *         imperatively (App's scrollToBottom, and the jump-on-new-message
 *         effects in ExplorarObras and GuidedStudy)
 *   options.threshold — px from the bottom still considered "at the bottom"
 */
export function useStickToBottom(ref, { threshold = 80 } = {}) {
  const pinnedRef = useRef(true);
  const [el, setEl] = useState(null);

  const attach = useCallback(
    (node) => {
      if (ref) ref.current = node;
      setEl(node);
    },
    [ref]
  );

  useEffect(() => {
    if (!el) return;

    const nearBottom = () =>
      el.scrollHeight - el.scrollTop - el.clientHeight <= threshold;

    // Re-evaluate on attach: a thread reopened from history mounts already
    // scrolled, and inheriting a stale `true` from a previous container would
    // yank the reader to the bottom of a conversation they meant to re-read.
    pinnedRef.current = nearBottom();

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
  }, [el, threshold]);

  return attach;
}

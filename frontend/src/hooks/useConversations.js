import { useStorage } from './useStorage';

/**
 * Give every message a send time, without ever moving one that already has it.
 *
 * saveConvo runs on every turn with the whole thread, so the naive version —
 * stamping Date.now() on whatever comes in — would restamp the older messages
 * each time and slide the whole conversation forward to the moment of the last
 * save. A reader would open a week-old thread and find every message sent in
 * the same second, and the day dividers would collapse into one.
 *
 * Messages carry their own `ts` from creation; this is a backstop, so that a
 * message created by code which forgot to stamp still gets a plausible time
 * instead of none. The id is the stable key for anything already persisted.
 */
function withTimestamps(msgs, previous) {
  const known = new Map((previous || []).map(m => [m.id, m.ts]));
  const now = Date.now();
  return msgs.map(m => (m.ts ? m : { ...m, ts: known.get(m.id) ?? now }));
}

export function useConversations() {
  const [conversations, setConversations] = useStorage('dialogando_convos', []);

  const saveConvo = (id, title, mode, msgs, sub = null) => {
    setConversations(prev => {
      const existing = prev.find(c => c.id === id);
      const entry = {
        id,
        title,
        mode,
        sub,
        msgs: withTimestamps(msgs, existing?.msgs),
        // `ts` has always meant "last saved" and still does — it is what the
        // history list sorts by. `createdAt` is the new one: when the thread
        // began. Conversations already in a reader's localStorage inherit their
        // existing `ts`, the closest thing to a start time ever recorded for
        // them, rather than having one invented.
        createdAt: existing?.createdAt ?? existing?.ts ?? Date.now(),
        ts: Date.now(),
        favorited: existing?.favorited || false,
      };
      if (existing) return prev.map(c => c.id === id ? entry : c);
      return [entry, ...prev].slice(0, 20);
    });
  };

  const deleteConvo = (id) => setConversations(prev => prev.filter(c => c.id !== id));

  const toggleConvoFavorite = (id) => {
    setConversations(prev =>
      prev.map(c => c.id === id ? { ...c, favorited: !c.favorited } : c)
    );
  };

  const loadConvo = (id) => conversations.find(c => c.id === id);
  const clearAll = () => setConversations([]);

  return { conversations, saveConvo, loadConvo, clearAll, deleteConvo, toggleConvoFavorite };
}

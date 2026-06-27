import { useStorage } from './useStorage';

export function useConversations() {
  const [conversations, setConversations] = useStorage('dialogando_convos', []);

  const saveConvo = (id, title, mode, msgs) => {
    setConversations(prev => {
      const existing = prev.find(c => c.id === id);
      const entry = { id, title, mode, msgs, ts: Date.now() };
      if (existing) return prev.map(c => c.id === id ? entry : c);
      return [entry, ...prev].slice(0, 20);
    });
  };

  const loadConvo = (id) => conversations.find(c => c.id === id);
  const clearAll = () => setConversations([]);

  return { conversations, saveConvo, loadConvo, clearAll };
}

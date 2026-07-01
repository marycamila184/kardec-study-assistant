import { useStorage } from './useStorage';

export function useFavorites() {
  const [favorites, setFavorites] = useStorage('dialogando_favs', []);

  const toggleFavorite = (msg) => {
    setFavorites(prev => {
      const exists = prev.some(f => f.id === msg.id);
      if (exists) return prev.filter(f => f.id !== msg.id);
      return [...prev, { id: msg.id, ia: msg.fullText || msg.ia, obra: msg.obra, ts: Date.now() }];
    });
  };

  const isFavorite = (id) => favorites.some(f => f.id === id);

  return { favorites, toggleFavorite, isFavorite };
}

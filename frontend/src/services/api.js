const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class ApiError extends Error {
  constructor(status, body) {
    super(body?.detail?.error || body?.detail || 'API error');
    this.status = status;
    this.body = body;
  }
}

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, body);
  return body;
}

// ── Book name mapping (matches BOOK_NAME_MAP in parsing_pipeline.py) ──────────
// lm and gen are not yet indexed — callers fall back to /chat for those.
export const BOOK_NAME_MAP = {
  le:  'O Livro dos Espíritos',
  lm:  'O Livro dos Médiuns',
  ese: 'O Evangelho Segundo o Espiritismo',
  ci:  'O Céu e o Inferno',
  gen: 'A Gênese',
};

// ── Item reference parser ─────────────────────────────────────────────────────
// Extracts item_number or chapter from strings like "O que é Deus? (Q.1)"
export function parseItemRef(itemString) {
  const qMatch = itemString.match(/\(Q\.(\d+)\)/);
  if (qMatch) return { item_number: qMatch[1], chapter: null };
  const capMatch = itemString.match(/\(cap\.\s*([IVXLCDM\d]+)\)/i);
  if (capMatch) return { item_number: null, chapter: capMatch[1] };
  return { item_number: null, chapter: null };
}

// ── Response mapping functions ────────────────────────────────────────────────

function mapChat(data) {
  return {
    hasDaObra: false,
    obra: null,
    ia: data.answer,
    sources: data.sources.map(s => ({
      book: s.book,
      item_number: s.item_number,
      excerpt: s.excerpt || null,
    })),
  };
}

function mapStudy(data, bookLabel, itemNumber) {
  const note = data.generation_failed
    ? '\n\n⚠️ A análise não pôde ser gerada completamente.'
    : '';
  const chapterTitle = data.sources[0]?.chapter_title;

  const partes = [];
  if (data.contexto) partes.push(data.contexto);
  if (data.conceitos_chave?.length) {
    partes.push('Conceitos-chave:\n' + data.conceitos_chave.map(c => `• ${c}`).join('\n'));
  }
  const ia = partes.join('\n\n') + note;

  const titleParts = [bookLabel, chapterTitle, itemNumber ? 'Q.' + itemNumber : null]
    .filter(Boolean);
  return {
    hasDaObra: true,
    obra: {
      title: titleParts.join(' — '),
      quote: data.original_text,
      citation: bookLabel + ' — Allan Kardec',
      context: chapterTitle || bookLabel,
    },
    ia,
    relatedItems: (data.related_items || []).map(r => ({
      book: r.book,
      chapter: r.chapter || null,
      item_number: r.item_number,
      preview: r.preview,
      conexao: r.conexao || null,
    })),
  };
}

function mapReflect(data) {
  const questions = data.reflection_questions
    .map((q, i) => `${i + 1}. ${q}`)
    .join('\n');
  const ia = [
    data.opening,
    data.doctrine_connection,
    questions ? 'Perguntas para reflexão:\n' + questions : '',
  ]
    .filter(Boolean)
    .join('\n\n');
  const relatedItems = (data.complementary_items || []).map(r => ({
    book: r.book,
    chapter: r.chapter || null,
    item_number: r.item_number,
    preview: r.preview,
    conexao: r.conexao || null,
  }));
  const sources = data.sources.map(s => ({
    book: s.book,
    item_number: s.item_number,
    excerpt: s.excerpt || null,
  }));
  return { hasDaObra: false, obra: null, ia, relatedItems, sources };
}

// ── Exported API functions ────────────────────────────────────────────────────

export async function chatMessage(question, history = []) {
  const data = await request('/chat', {
    method: 'POST',
    body: JSON.stringify({ question, history }),
  });
  return mapChat(data);
}

export async function studyItem(book, item_number, chapter = null) {
  const data = await request('/study', {
    method: 'POST',
    body: JSON.stringify({ book, item_number, chapter }),
  });
  return mapStudy(data, book, item_number);
}

export async function reflectSituation(situation) {
  const data = await request('/reflect', {
    method: 'POST',
    body: JSON.stringify({ situation }),
  });
  return mapReflect(data);
}

// Returns raw { date, content, source }
export async function getEvangelho() {
  return request('/evangelho');
}

// Returns raw [{ id, title, description, level, step_count }]
export async function getPaths() {
  return request('/paths');
}

// Returns raw { id, title, description, level, steps: [{book, chapter?, item_number, label}] }
export async function getPath(pathId) {
  return request('/paths/' + pathId);
}

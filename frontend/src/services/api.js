import { formatItemRef } from '../utils/format';

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
    suggestedMode: data.suggested_mode || null,
    suggestedItemNumber: data.suggested_item_number || null,
    suggestedBook: data.suggested_book || null,
    suggestedQuestions: data.suggested_questions || [],
    sources: data.sources.map(s => ({
      book: s.book,
      chapter: s.chapter || null,
      chapter_ref: s.chapter_ref || null,
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

  const titleParts = [bookLabel, chapterTitle, itemNumber ? formatItemRef(bookLabel, itemNumber) : null]
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

// mapReflect and reflectSituation below are unused now — Refletir is switched
// off for production — the mode is disconnected, not deleted. See
// docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md
function mapReflect(data) {
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
  const questions = (data.reflection_questions || [])
    .map((q, i) => `${i + 1}. ${q}`)
    .join('\n');
  const doctrineConnection = data.generation_failed
    ? '⚠️ A reflexão não pôde ser gerada completamente. Tente novamente.'
    : data.doctrine_connection;
  const fullText = [
    data.opening,
    doctrineConnection,
    questions ? 'Perguntas para reflexão:\n' + questions : '',
  ]
    .filter(Boolean)
    .join('\n\n');
  return {
    hasDaObra: false,
    obra: null,
    isReflection: true,
    isClosing: !!data.is_closing,
    opening: data.opening,
    ia: doctrineConnection,
    fullText,
    reflectionQuestions: data.reflection_questions || [],
    relatedItems,
    sources,
    suggestedMode: data.suggested_mode || null,
    suggestedItemNumber: data.suggested_item_number || null,
    suggestedBook: data.suggested_book || null,
  };
}

// ── Exported API functions ────────────────────────────────────────────────────

export async function chatMessage(question, history = [], bookFilter = null, currentMode = null) {
  const data = await request('/chat', {
    method: 'POST',
    body: JSON.stringify({
      question,
      history,
      book_filter: bookFilter || undefined,
      current_mode: currentMode || undefined,
    }),
  });
  return mapChat(data);
}

// POSTs to an SSE endpoint and returns the `done` payload, calling
// onEvent(name, payload) for every event that arrives before it.
//
// The `done` event is the source of truth: whatever was accumulated from the
// tokens gets replaced by it, so what ends up on screen is always identical to
// what the non-streaming endpoint would have returned.
//
// Throws on any transport problem, so callers can fall back to the plain
// endpoint — nobody may be left holding half an answer.
async function streamSSE(path, body, onEvent) {
  const res = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(res.status, await res.json().catch(() => ({})));
  if (!res.body) throw new Error('streaming not supported by this browser');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let done = null;

  for (;;) {
    const { value, done: finished } = await reader.read();
    if (finished) break;
    buffer += decoder.decode(value, { stream: true });
    // SSE frames are separated by a blank line; the tail may be a partial frame.
    const frames = buffer.split('\n\n');
    buffer = frames.pop();
    for (const frame of frames) {
      const event = frame.match(/^event: (.+)$/m)?.[1];
      const data = frame.match(/^data: (.+)$/m)?.[1];
      if (!event || !data) continue;
      const payload = JSON.parse(data);
      if (event === 'done') done = payload;
      else onEvent(event, payload);
    }
  }

  if (!done) throw new Error('stream ended without a done event');
  return done;
}

// Same answer as chatMessage, streamed. Falls to the caller to recover.
export async function chatMessageStream(
  question, history = [], bookFilter = null, currentMode = null, onToken = () => {},
) {
  const done = await streamSSE('/chat/stream', {
    question,
    history,
    book_filter: bookFilter || undefined,
    current_mode: currentMode || undefined,
  }, (event, payload) => { if (event === 'token') onToken(payload.text); });
  return mapChat(done);
}

export async function studyItem(book, item_number, chapter = null) {
  const data = await request('/study', {
    method: 'POST',
    body: JSON.stringify({ book, item_number, chapter }),
  });
  return mapStudy(data, book, item_number);
}

// Same answer as studyItem, streamed. The tokens carry the `contexto` field
// only — conceitos-chave, related items and sources arrive whole with `done`,
// which is also what mapStudy runs on, so a streamed study is identical to
// POST /study.
//
// onSource fires once, before any token: the passage itself is known from
// retrieval, so it can be on screen while the explanation is still being
// written. onSource receives what mapStudy would have produced for the passage
// alone, so the caller renders it the same way in both lanes.
export async function studyItemStream(
  book, item_number, chapter = null, onToken = () => {}, onSource = () => {},
) {
  const done = await streamSSE('/study/stream', { book, item_number, chapter },
    (event, payload) => {
      if (event === 'token') onToken(payload.text);
      else if (event === 'source') {
        onSource(mapStudy({
          ...payload, contexto: '', conceitos_chave: [], perguntas: [],
          related_items: [], generation_failed: false,
        }, book, item_number));
      }
    });
  return mapStudy(done, book, item_number);
}

// Unused now — Refletir is switched off for production — the mode is
// disconnected, not deleted. See
// docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md
export async function reflectSituation(situation, history = [], currentMode = null) {
  const data = await request('/reflect', {
    method: 'POST',
    body: JSON.stringify({
      situation,
      conversation_history: history,
      current_mode: currentMode || undefined,
    }),
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

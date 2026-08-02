import { formatItemRef } from '../utils/format';
import { sessionId } from './consent';

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class ApiError extends Error {
  constructor(status, body) {
    super(body?.detail?.error || body?.detail || 'API error');
    this.status = status;
    this.body = body;
  }
}

// Os dois caminhos de rede — request e streamSSE — passam por aqui, e são os
// únicos lugares do app que montam headers. O X-Session-Id só existe quando há
// consentimento: sessionId() devolve null sem ele, e a ausência do header É a
// recusa do lado do servidor. Nenhuma função de chamada precisou mudar.
function headers() {
  const id = sessionId();
  return {
    'Content-Type': 'application/json',
    ...(id ? { 'X-Session-Id': id } : {}),
  };
}

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: headers(),
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
  // When the question named a specific item, the answer carries the passage
  // itself and it renders as the "Da Obra" block — Kardec's words above the
  // explanation and visibly apart from it. Free study runs through /chat now,
  // and a source chip you have to click is not the same separation.
  const studied = data.studied_item || null;
  return {
    // O turno registrado, para o voto poder se referir a ele. Null quando o
    // turno não foi logado — e aí os polegares simplesmente não aparecem.
    turnId: data.turn_id || null,
    hasDaObra: !!studied,
    obra: studied ? {
      title: [studied.book, studied.chapter_title,
        studied.item_number ? formatItemRef(studied.book, studied.item_number) : null]
        .filter(Boolean).join(' — '),
      quote: studied.excerpt,
      citation: studied.book + ' — Allan Kardec',
      context: studied.chapter_title || studied.book,
    } : null,
    ia: data.answer,
    suggestedMode: data.suggested_mode || null,
    suggestedItemNumber: data.suggested_item_number || null,
    suggestedBook: data.suggested_book || null,
    suggestedQuestions: data.suggested_questions || [],
    // The shape this answer was written with. The caller carries it into the
    // next turn — without that, a reader who asks for citations gets them once
    // and then silently loses them, which reads as the app forgetting.
    profile: data.profile || null,
    inlineRefs: data.inline_refs || [],
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
    // Null no evento `source` do stream, que chega com um payload sintético
    // sem turn_id — e é o certo: o voto só existe depois que a resposta
    // terminou.
    turnId: data.turn_id || null,
    hasDaObra: true,
    // True by construction, never by inference from hasDaObra: hasDaObra is
    // also true on /chat when free study resolves a named item, but /chat
    // still runs a normal cross-book retrieval alongside that and can cite
    // passages outside the resolved chapter. /study's inline refs are
    // resolved against the chapter context only — chapter_commentary in
    // src/rag/retriever.py filters by book AND chapter — so every /study ref
    // is guaranteed to be from the chapter already on screen. Do not fold
    // this back into hasDaObra.
    isStudy: true,
    obra: {
      title: titleParts.join(' — '),
      quote: data.original_text,
      citation: bookLabel + ' — Allan Kardec',
      context: chapterTitle || bookLabel,
    },
    ia,
    // Missing on the stream's synthetic `source` payload (no inline_refs key
    // at all, since the answer hasn't been generated yet) — `|| []` keeps
    // that an empty array rather than undefined, same as mapChat.
    inlineRefs: data.inline_refs || [],
    relatedItems: (data.related_items || []).map(r => ({
      book: r.book,
      chapter: r.chapter || null,
      item_number: r.item_number,
      preview: r.preview,
      conexao: r.conexao || null,
    })),
    // The chapter's other items.
    //
    // The heading used to say "usados na explicação" while listing everything
    // fed to the prompt — on the daily passage of 2026-07-28 that promised two
    // items the answer had never marked. Showing only the cited ones fixed the
    // honesty and left a study screen bare on most turns, which is its own kind
    // of wrong: having more of the chapter within reach is useful whether or
    // not this particular answer leaned on it. So: everything is listed, and
    // the label promises nothing about use.
    //
    // chapter_ref is copied through so IABlock can pass it to formatSourceRef —
    // without it these buttons show only "item N" and silently drop the
    // chapter, one of the label failures raised on 2026-07-28.
    //
    // No cited-first sort here anymore: IABlock filters the cited items out of
    // this list entirely once it renders them as inline links, so an ordering
    // that used to promote them to the front has nothing left to promote.
    chapterContext: (data.chapter_context || []).map(c => ({
      book: c.book,
      chapter: c.chapter_title || null,
      chapter_ref: c.chapter_ref || null,
      item_number: c.item_number,
      excerpt: c.excerpt,
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

export async function chatMessage(
  question, history = [], bookFilter = null, currentMode = null, profile = null,
  chapterFilter = null,
) {
  const data = await request('/chat', {
    method: 'POST',
    body: JSON.stringify({
      question,
      history,
      book_filter: bookFilter || undefined,
      // Only Explorar's Evangelho topics set this; see chapterFilterFromTopic.
      chapter_filter: chapterFilter || undefined,
      current_mode: currentMode || undefined,
      profile: profile || undefined,
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
    headers: headers(),
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
  profile = null,
) {
  const done = await streamSSE('/chat/stream', {
    question,
    history,
    book_filter: bookFilter || undefined,
    current_mode: currentMode || undefined,
    profile: profile || undefined,
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

// O voto numa resposta. Não devolve nada e nunca lança para o chamador: um erro
// de rede aqui não pode virar um alerta na cara de quem só quis dizer que a
// resposta foi ruim.
//
// Funciona com ou sem consentimento — {turn_id, vote} não descreve pessoa —, e
// por isso não checa nada antes de enviar.
export async function sendFeedback(turnId, vote) {
  if (!turnId) return;
  try {
    await fetch(BASE + '/feedback', {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ turn_id: turnId, vote }),
    });
  } catch {
    /* silencioso por desenho */
  }
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

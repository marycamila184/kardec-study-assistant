import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import Sidebar from './components/layout/Sidebar';
import TopBar from './components/layout/TopBar';
import HomeLauncher from './components/layout/HomeLauncher';
import MobileBottomNav from './components/layout/MobileBottomNav';
import Onboarding from './components/modals/Onboarding';
import SettingsPanel from './components/modals/SettingsPanel';
import ShareModal from './components/modals/ShareModal';
import RelatedItemsModal from './components/modals/RelatedItemsModal';
import TrilhaCompleteModal from './components/modals/TrilhaCompleteModal';
import EstudarPicker from './components/modes/EstudarPicker';
import RefletirPicker from './components/modes/RefletirPicker';
import GuidedStudy from './components/modes/GuidedStudy';
import ExplorarObras from './components/modes/ExplorarObras';
import IntroObras from './components/modes/IntroObras';
import UserBubble from './components/chat/UserBubble';
import AIMessage from './components/chat/AIMessage';
import LoadingDots from './components/chat/LoadingDots';
import InputBar from './components/chat/InputBar';
import { useTheme } from './hooks/useTheme';
import { useStorage } from './hooks/useStorage';
import { useConversations } from './hooks/useConversations';
import { useReminder } from './hooks/useReminder';
import { useStickToBottom } from './hooks/useStickToBottom';
import { formatItemRef } from './utils/format';
import { lightTheme } from './constants/theme';
import { MODES } from './constants/modes';
import {
  chatMessage, studyItem, reflectSituation,
  getEvangelho, getPaths, getPath,
  BOOK_NAME_MAP, parseItemRef,
} from './services/api';

const QUICK_ACTIONS = [
  { label: '📄 Ler original' },
  { label: '💡 Explicar simples' },
  { label: '🪞 Reflexão' },
  { label: '📚 Relacionados' },
];

const MODE_PLACEHOLDER = {
  estudar:  'Ex: Explique a questão 132 do Livro dos Espíritos…',
  duvida:   'Ex: O que Kardec fala sobre reencarnação?',
  refletir: 'Ex: Estou passando por um conflito familiar…',
};

const MODE_PLACEHOLDER_MOBILE = {
  estudar:  'Digite sua dúvida…',
  duvida:   'Pergunte sobre a doutrina…',
  refletir: 'Descreva sua situação…',
};

// Starter questions for the Dialogar empty state — its only consumer.
// Doctrinal questions only: "Como posso ter mais paz no dia a dia?" used to sit
// here and was a Refletir prompt wearing a 🪞, which is a different mode with a
// different contract (no advice, questions back rather than answers).
const SUGGESTIONS = [
  { icon: '📖', label: 'O que é o Espiritismo?' },
  { icon: '💬', label: 'Qual a diferença entre alma, perispírito e espírito?' },
  { icon: '🔄', label: 'O que é a reencarnação?' },
];

const ERROR_MSG = {
  hasDaObra: false, obra: null,
  ia: 'Não foi possível obter uma resposta. Verifique sua conexão e tente novamente.',
};

// Maps the client's mode state to the orchestrator's intent vocabulary, so the
// backend never nudges the user toward the mode they're already in. `mode` is
// null on the home screen, which sends no requests — but every dynamic lookup
// is guarded with `|| null` at the call site anyway, because an undefined
// reaching the backend would silently re-enable self-nudging rather than fail
// loudly.
const MODE_TO_INTENT = { duvida: 'tirar_duvida', refletir: 'refletir', estudar: 'estudar_obra' };

export default function App() {

  // ── Theme ───────────────────────────────────────────────────────────────
  const { darkMode, toggleDark, theme } = useTheme();

  // ── Persistence ─────────────────────────────────────────────────────────
  const [onboarded,    setOnboarded]    = useStorage('dialogando_onboarded', false);
  const [fontSize,     setFontSize]     = useStorage('dialogando_fontsize', 'medium');
  const [reminderOn,       setReminderOn]       = useStorage('dialogando_reminder_on', false);
  const [reminderTime,     setReminderTime]     = useStorage('dialogando_reminder_time', '08:00');
  const [completedTrilhas, setCompletedTrilhas] = useStorage('dialogando_completed_trilhas', []);
  const [notifPerm,    setNotifPerm]    = useState(() => typeof Notification !== 'undefined' ? Notification.permission : 'default');
  const { conversations, saveConvo, deleteConvo, toggleConvoFavorite } = useConversations();

  // ── API state ────────────────────────────────────────────────────────────
  const [evangelhoData, setEvangelhoData] = useState(null);
  const [paths,         setPaths]         = useState([]);
  const [pathsLoading,  setPathsLoading]  = useState(true);

  // ── UI State ────────────────────────────────────────────────────────────
  const [mode,          setMode]         = useState(null);
  const [input,         setInput]        = useState('');
  const [msgs,          setMsgs]         = useState([]);
  const [loading,       setLoading]      = useState(false);
  const [estudarSub,    setEstudarSub]   = useState('picker');
  const [refletirSub,   setRefletirSub] = useState('picker');
  const [activeTrilha,  setActiveTrilha] = useState(null);
  const [guidedStep,    setGuidedStep]   = useState(0);
  const [guidedMsgs,    setGuidedMsgs]   = useState([]);
  const [guidedLoading, setGuidedLoading]= useState(false);
  const [explorarMsgs,  setExplorarMsgs] = useState([]);
  const [explorarLoad,  setExplorarLoad] = useState(false);
  const [explorarConvoMeta, setExplorarConvoMeta] = useState(null); // { id, title } | null
  const explorarConvoMetaRef = useRef(null);
  const [showSettings,  setShowSettings] = useState(false);
  const [shareMsg,      setShareMsg]     = useState(null);
  const [relatedModal,  setRelatedModal] = useState(null);
  const [trilhaCompleteModal, setTrilhaCompleteModal] = useState(null);
  const [convoId,       setConvoId]      = useState(null);
  const [isMobile,      setIsMobile]     = useState(() => window.innerWidth < 768);
  const [drawerOpen,    setDrawerOpen]   = useState(false);
  const msgsRef = useRef(null);
  const requestIdRef = useRef(0);
  // Bumped whenever a message thread is replaced or reset (mode switch, convo
  // load/delete, book change, trilha start). Slow quick-action / trecho replies
  // capture it before their await and drop themselves if the thread they were
  // meant for is gone — unlike requestIdRef, a concurrent *send* doesn't bump
  // it, since interleaved appends to the same thread are fine.
  const threadEpochRef = useRef(0);
  useStickToBottom(msgsRef); // follow the typewriter reveal to the bottom

  // ── On-mount: fetch evangelho + paths ────────────────────────────────────
  useEffect(() => {
    getEvangelho().then(setEvangelhoData).catch(() => {});
    getPaths()
      .then(setPaths)
      .catch(() => setPaths([]))
      .finally(() => setPathsLoading(false));
  }, []);

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  // Scrolls after the next couple of paint frames, once new content has
  // actually been laid out, instead of polling scrollTop for seconds.
  const scrollToBottom = () => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        if (msgsRef.current) msgsRef.current.scrollTop = msgsRef.current.scrollHeight;
      });
    });
  };

  // ── Font size helper ─────────────────────────────────────────────────────
  const msgFontSize = { small: '14px', medium: '15px', large: '17px' }[fontSize] || '15px';

  // ── Conversation delete — clears active state if the deleted convo is current ─
  const handleDeleteConvo = (id) => {
    deleteConvo(id);
    // Active trilha: guided messages carry tutor_* ids, not the convo id, so
    // match against the trilha itself and clear the guided state directly.
    if (activeTrilha && id === 'trilha_' + activeTrilha.id) {
      threadEpochRef.current += 1;
      setActiveTrilha(null); setGuidedMsgs([]); setGuidedStep(0); setGuidedLoading(false);
      if (mode === 'estudar') setEstudarSub('picker');
      return;
    }
    const isActive = id === convoId || id === explorarConvoMeta?.id;
    if (isActive) {
      threadEpochRef.current += 1;
      setMsgs([]); setConvoId(null); setLoading(false); setInput('');
      setExplorarMsgs([]); setExplorarConvoMeta(null); explorarConvoMetaRef.current = null;
      // Home, not Dialogar: the reader deleted the thread they were reading, so
      // dropping them into an empty chat picks a mode on their behalf.
      setMode(null);
    }
  };

  // ── Mode switching ───────────────────────────────────────────────────────
  const switchMode = (m) => {
    requestIdRef.current += 1; // invalidate any in-flight sendText for the old mode
    threadEpochRef.current += 1;
    setMode(m); setMsgs([]); setLoading(false); setInput(''); setConvoId(null);
    if (m === 'estudar') setEstudarSub('picker');
    if (m === 'refletir') setRefletirSub('picker');
  };

  // Returning home is "start a new conversation": mode is a property of a
  // conversation (it is saved with it and restored by handleLoadConvo), so there
  // is no separate "switch mode" action to model. The current thread is already
  // in history — saveConvo runs every turn — so this clears the view, not the
  // content.
  //
  // switchMode only resets estudarSub/refletirSub when switching *into* those
  // modes, so going home must reset them explicitly or the next entry into
  // Estudar reopens the guided view the reader thought they had left.
  const newConvo = () => {
    switchMode(null);
    setEstudarSub('picker');
    setRefletirSub('picker');
    setExplorarMsgs([]);
    setExplorarConvoMeta(null);
    explorarConvoMetaRef.current = null;
  };

  // ── Main chat send (dúvida + refletir) ───────────────────────────────────
  // Assistant turn for /chat history. Study/trecho replies (mode 'duvida' but
  // produced by /study) carry the original passage in `obra.quote` while `ia`
  // holds only contexto+conceitos — without the passage, /chat re-condenses and
  // retrieves against a nonsense user turn ("Estudo diário de hoje") and loses
  // all grounding. Prepend the studied passage so follow-ups stay coherent.
  const buildChatHistoryContent = (m) => {
    const parts = [];
    if (m.obra?.quote) {
      const label = m.obra.title ? `Trecho estudado — ${m.obra.title}` : 'Trecho estudado';
      parts.push(`[${label}]\n${m.obra.quote}`);
    }
    if (m.ia) parts.push(m.ia);
    return parts.join('\n\n');
  };

  const sendText = async (txt) => {
    if (!txt) return;
    const userMsg = { id: 'u' + Date.now(), isUser: true, isAI: false, text: txt };
    const newMsgs = [...msgs, userMsg];
    setMsgs(newMsgs); setInput(''); setLoading(true);
    const id = convoId || ('c' + Date.now());
    setConvoId(id);
    saveConvo(id, txt.slice(0, 48), mode, newMsgs);
    scrollToBottom();
    const requestId = ++requestIdRef.current;
    const requestMode = mode;

    try {
      let reply;
      if (requestMode === 'refletir') {
        reply = await reflectSituation(txt, buildReflectHistory(msgs), MODE_TO_INTENT[requestMode] || null);
      } else {
        const history = msgs.map(m => ({
          role: m.isUser ? 'user' : 'assistant',
          content: m.isUser ? m.text : buildChatHistoryContent(m),
        }));
        reply = await chatMessage(txt, history, null, MODE_TO_INTENT[requestMode] || null);
      }
      if (requestId !== requestIdRef.current) return; // user switched modes meanwhile
      const aiMsg = { id: 'a' + Date.now(), isUser: false, isAI: true, ...reply };
      const finalMsgs = [...newMsgs, aiMsg];
      setMsgs(finalMsgs);
      saveConvo(id, txt.slice(0, 48), mode, finalMsgs);
    } catch (err) {
      console.error('sendText failed:', err);
      if (requestId !== requestIdRef.current) return;
      setMsgs([...newMsgs, { id: 'a' + Date.now(), isUser: false, isAI: true, ...ERROR_MSG }]);
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
        scrollToBottom();
      }
    }
  };

  // ── Build {role, content} history for a Refletir thread from current msgs ──
  const buildReflectHistory = (msgs) => msgs.map(m => {
    if (m.isUser) return { role: 'user', content: m.text };
    const questions = (m.reflectionQuestions || []).map((q, i) => `${i + 1}. ${q}`).join('\n');
    const content = [
      m.opening,
      m.ia,
      questions ? `Perguntas de reflexão já oferecidas:\n${questions}` : '',
    ].filter(Boolean).join('\n\n');
    return { role: 'assistant', content };
  });

  // ── Continue a Refletir thread via a clicked reflection-question button ───
  const handleReflectionQuestionClick = async (question) => {
    const history = buildReflectHistory(msgs);
    const userMsg = { id: 'u' + Date.now(), isUser: true, isAI: false, text: question };
    const newMsgs = [...msgs, userMsg];
    setMsgs(newMsgs); setLoading(true);
    const id = convoId || ('c' + Date.now());
    setConvoId(id);
    saveConvo(id, question.slice(0, 48), mode, newMsgs);
    scrollToBottom();
    const requestId = ++requestIdRef.current;

    try {
      // 'refletir' as current_mode so the orchestrator never self-nudges
      // toward Refletir inside a Refletir thread (sendText does the same).
      const reply = await reflectSituation(question, history, MODE_TO_INTENT.refletir);
      if (requestId !== requestIdRef.current) return; // user switched modes meanwhile
      const aiMsg = { id: 'a' + Date.now(), isUser: false, isAI: true, ...reply };
      const finalMsgs = [...newMsgs, aiMsg];
      setMsgs(finalMsgs);
      saveConvo(id, question.slice(0, 48), mode, finalMsgs);
    } catch (err) {
      console.error('handleReflectionQuestionClick failed:', err);
      if (requestId !== requestIdRef.current) return;
      setMsgs([...newMsgs, { id: 'a' + Date.now(), isUser: false, isAI: true, ...ERROR_MSG }]);
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
        scrollToBottom();
      }
    }
  };

  const handleSend = () => sendText(input.trim());

  // ── Quick action executor (shared across chat / guided / explorar) ────────
  const runQuickAction = async (label, msg, appendMsg, setLoad) => {
    const quote = msg.obra?.quote || msg.ia || '';
    const snippet = quote.slice(0, 400);
    const epoch = threadEpochRef.current;
    // Drop late replies if the target thread was replaced meanwhile.
    const append = (m) => { if (epoch === threadEpochRef.current) appendMsg(m); };

    if (label === '📄 Ler original') {
      if (msg.obra?.quote) {
        append({
          id: 'a' + Date.now(), isUser: false, isAI: true,
          hasDaObra: true, obra: { ...msg.obra, title: 'Texto original' }, ia: '',
        });
      }
      scrollToBottom();
      return;
    }

    if (label === '📚 Relacionados') {
      const related = msg.relatedItems || [];
      if (related.length > 0) {
        setRelatedModal({ items: related, appendMsg, setLoad });
      }
      return;
    }

    const userText = label === '💡 Explicar simples'
      ? `Explique de forma mais simples: "${snippet}"`
      : '🪞 Reflexão sobre este trecho';
    append({ id: 'u' + Date.now(), isUser: true, isAI: false, text: userText });
    setLoad(true);
    scrollToBottom();
    try {
      const reply = label === '🪞 Reflexão'
        ? await reflectSituation(snippet)
        : await chatMessage(`Explique de forma mais simples: "${snippet}"`);
      append({ id: 'a' + Date.now(), isUser: false, isAI: true, ...reply });
    } catch (err) {
      console.error('runQuickAction failed:', err);
      append({ id: 'a' + Date.now(), isUser: false, isAI: true, ...ERROR_MSG });
    } finally {
      setLoad(false);
      scrollToBottom();
    }
  };

  const handleQuickAction       = (label, msg) =>
    runQuickAction(label, msg, m => setMsgs(prev => [...prev, m]), setLoading);
  const handleGuidedQuickAction = (label, msg) =>
    runQuickAction(label, msg, m => setGuidedMsgs(prev => [...prev, m]), setGuidedLoading);
  const handleExplorarQuickAction = (label, msg) =>
    runQuickAction(label, msg, m => setExplorarMsgs(prev => [...prev, m]), setExplorarLoad);

  // ── In-context "Tenho uma dúvida" (Guided/Explorar) ────────────────────────
  const askDuvida = async (displayText, queryText, appendMsg, setLoad, bookFilter = null) => {
    const epoch = threadEpochRef.current;
    const append = (m) => { if (epoch === threadEpochRef.current) appendMsg(m); };
    append({ id: 'u' + Date.now(), isUser: true, isAI: false, text: displayText });
    setLoad(true);
    scrollToBottom();
    try {
      const reply = await chatMessage(queryText, [], bookFilter);
      append({ id: 'a' + Date.now(), isUser: false, isAI: true, ...reply });
    } catch (err) {
      console.error('askDuvida failed:', err);
      append({ id: 'a' + Date.now(), isUser: false, isAI: true, ...ERROR_MSG });
    } finally {
      setLoad(false);
      scrollToBottom();
    }
  };
  const handleGuidedDuvida = (displayText, queryText) =>
    askDuvida(displayText, queryText, m => setGuidedMsgs(prev => [...prev, m]), setGuidedLoading);
  const handleExplorarDuvida = (displayText, queryText, bookFilter) => askDuvida(displayText, queryText, m => {
    setExplorarMsgs(prev => {
      const updated = [...prev, m];
      if (explorarConvoMetaRef.current) saveConvo(explorarConvoMetaRef.current.id, explorarConvoMetaRef.current.title, 'estudar', updated, 'explorar');
      return updated;
    });
  }, setExplorarLoad, bookFilter);

  // ── Guided study ──────────────────────────────────────────────────────────
  const startTrilha = async (pathSummary) => {
    threadEpochRef.current += 1; // resets guidedMsgs — drop stale quick-action replies
    setEstudarSub('guided');
    setGuidedStep(0); setGuidedMsgs([]); setGuidedLoading(true);
    let pathDetail;
    try {
      pathDetail = await getPath(pathSummary.id);
    } catch (err) {
      console.error('startTrilha failed:', err);
      setGuidedLoading(false); setEstudarSub('picker'); return;
    }
    setActiveTrilha(pathDetail);
    await presentGuidedStep(pathDetail, 0, []);
  };

  const presentGuidedStep = async (trilha, stepIdx, existingMsgs) => {
    setGuidedLoading(true);
    const step = trilha.steps[stepIdx];
    let tutorMsg;
    try {
      const reply = await studyItem(step.book, step.item_number, step.chapter || null);
      tutorMsg = {
        id: 'tutor_' + stepIdx,
        isUser: false, isAI: true,
        ...reply,
        obra: reply.obra
          ? { ...reply.obra, title: `${step.book} — ${step.label} · Passo ${stepIdx + 1} de ${trilha.steps.length}` }
          : null,
      };
    } catch (err) {
      console.error('presentGuidedStep failed:', err);
      tutorMsg = {
        id: 'tutor_' + stepIdx,
        isUser: false, isAI: true, hasDaObra: false, obra: null,
        ia: `Não foi possível carregar "${step.label}". Tente novamente.`,
      };
    }
    const updatedMsgs = [...existingMsgs, tutorMsg];
    setGuidedMsgs(updatedMsgs);
    saveConvo('trilha_' + trilha.id, trilha.title, 'estudar', updatedMsgs, 'guided');
    setGuidedLoading(false);
    scrollToBottom();
  };

  const handleGuidedNext = async () => {
    const next = guidedStep + 1;
    if (next >= activeTrilha.steps.length) {
      setCompletedTrilhas(prev => prev.includes(activeTrilha.id) ? prev : [...prev, activeTrilha.id]);
      const lastMsg = guidedMsgs.reduce((last, m) => (m.isAI && m.hasDaObra) ? m : last, null);
      setTrilhaCompleteModal({ trilha: activeTrilha, lastMsg });
      return;
    }
    setGuidedStep(next);
    await presentGuidedStep(activeTrilha, next, guidedMsgs);
  };

  // ── Explorar Obras ────────────────────────────────────────────────────────
  const handleAskTopic = async (query, obraId) => {
    const userMsg = { id: 'eu' + Date.now(), isUser: true, isAI: false, text: query };
    setExplorarMsgs([userMsg]); setExplorarLoad(true);

    const bookName = BOOK_NAME_MAP[obraId];
    const { item_number, chapter } = parseItemRef(query);

    let reply;
    try {
      if (item_number && bookName) {
        reply = await studyItem(bookName, item_number, chapter);
      } else {
        reply = await chatMessage(query, [], bookName || null);
      }
    } catch (err) {
      console.error('handleAskTopic failed:', err);
      if (err.status === 404) {
        try { reply = await chatMessage(query); }
        catch (err2) {
          console.error('handleAskTopic fallback failed:', err2);
          reply = { hasDaObra: false, obra: null, ia: 'Não foi possível obter uma resposta.' };
        }
      } else {
        reply = { hasDaObra: false, obra: null, ia: 'Não foi possível obter uma resposta.' };
      }
    } finally {
      setExplorarLoad(false);
    }

    const aiMsg = { id: 'ea' + Date.now(), isUser: false, isAI: true, ...reply };
    const convoId2 = 'explorar_' + Date.now();
    const title = query.slice(0, 48);
    const meta = { id: convoId2, title };
    setExplorarConvoMeta(meta);
    explorarConvoMetaRef.current = meta;
    saveConvo(convoId2, title, 'estudar', [userMsg, aiMsg], 'explorar');
    setExplorarMsgs([userMsg, aiMsg]);
    scrollToBottom();
  };

  // ── Explorar Obras: free-text chat (appends to existing conversation) ────────
  const handleExplorarChat = async (query, obraId) => {
    const userMsg = { id: 'eu' + Date.now(), isUser: true, isAI: false, text: query };
    const prevMsgs = explorarMsgs;
    setExplorarMsgs([...prevMsgs, userMsg]);
    setExplorarLoad(true);

    const bookName = BOOK_NAME_MAP[obraId];
    const { item_number, chapter } = parseItemRef(query);

    // buildChatHistoryContent (not m.ia) so /study replies keep the studied
    // passage in history — see the grounding note above sendText.
    const history = prevMsgs
      .filter(m => m.isUser || m.isAI)
      .slice(-6)
      .map(m => ({ role: m.isUser ? 'user' : 'assistant', content: m.isUser ? m.text : buildChatHistoryContent(m) }))
      .filter(h => h.content);

    let reply;
    try {
      if (item_number && bookName) {
        reply = await studyItem(bookName, item_number, chapter);
      } else {
        reply = await chatMessage(query, history, bookName || null);
      }
    } catch (err) {
      console.error('handleExplorarChat failed:', err);
      reply = { hasDaObra: false, obra: null, ia: 'Não foi possível obter uma resposta.' };
    }

    setExplorarLoad(false);
    const aiMsg = { id: 'ea' + Date.now(), isUser: false, isAI: true, ...reply };
    const updatedMsgs = [...prevMsgs, userMsg, aiMsg];

    const meta = explorarConvoMetaRef.current;
    if (meta) {
      saveConvo(meta.id, meta.title, 'estudar', updatedMsgs, 'explorar');
    } else {
      const convoId2 = 'explorar_' + Date.now();
      const title = query.slice(0, 48);
      const newMeta = { id: convoId2, title };
      setExplorarConvoMeta(newMeta);
      explorarConvoMetaRef.current = newMeta;
      saveConvo(convoId2, title, 'estudar', updatedMsgs, 'explorar');
    }
    setExplorarMsgs(updatedMsgs);
  };

  // Resolve which item the "Estudar este item completo" button should open.
  // Prefers the backend-extracted reference; falls back to the retrieved
  // sources so the button never regresses versus the old sources[0] behavior.
  const resolveStudyTarget = (msg) => {
    const sources = msg.sources || [];
    // chapter must be the machine id (chapter_ref, e.g. "CAPÍTULO II") that
    // /study filters on — source.chapter holds the display title, which the
    // backend would never match (404).
    if (msg.suggestedItemNumber) {
      const match = sources.find(s =>
        s.item_number === msg.suggestedItemNumber &&
        (!msg.suggestedBook || s.book === msg.suggestedBook)
      );
      const book = msg.suggestedBook || match?.book || sources[0]?.book || null;
      if (!book) return null;
      return { book, item_number: msg.suggestedItemNumber, chapter: match?.chapter_ref || null };
    }
    const first = sources[0];
    if (!first?.item_number) return null;
    return { book: first.book, item_number: first.item_number, chapter: first.chapter_ref || null };
  };

  // ── Suggested-mode: jump from /chat to a full item study in Explorar ────────
  const handleGoStudyItem = async (source) => {
    setMode('estudar'); setEstudarSub('explorar');
    const label = `${source.book}, ${formatItemRef(source.book, source.item_number)}`;
    const userMsg = { id: 'eu' + Date.now(), isUser: true, isAI: false, text: label };
    setExplorarMsgs([userMsg]); setExplorarLoad(true);
    setExplorarConvoMeta(null); explorarConvoMetaRef.current = null;
    try {
      const reply = await studyItem(source.book, source.item_number, source.chapter || null);
      const aiMsg = { id: 'ea' + Date.now(), isUser: false, isAI: true, ...reply };
      const meta = { id: 'explorar_' + Date.now(), title: label };
      setExplorarConvoMeta(meta); explorarConvoMetaRef.current = meta;
      saveConvo(meta.id, label, 'estudar', [userMsg, aiMsg], 'explorar');
      setExplorarMsgs([userMsg, aiMsg]);
    } catch (err) {
      console.error('handleGoStudyItem failed:', err);
      setExplorarMsgs([userMsg, { id: 'ea' + Date.now(), isUser: false, isAI: true, ...ERROR_MSG }]);
    } finally {
      setExplorarLoad(false);
    }
  };

  // ── Suggested-mode: jump from /chat to a Refletir thread seeded with the question ──
  const handleGoReflect = async (situationText) => {
    if (!situationText) return;
    switchMode('refletir');
    setRefletirSub('chat');
    const userMsg = { id: 'u' + Date.now(), isUser: true, isAI: false, text: situationText };
    setMsgs([userMsg]); setLoading(true);
    const id = 'c' + Date.now();
    setConvoId(id);
    saveConvo(id, situationText.slice(0, 48), 'refletir', [userMsg]);
    scrollToBottom();
    const requestId = ++requestIdRef.current;
    try {
      const reply = await reflectSituation(situationText, [], 'refletir');
      if (requestId !== requestIdRef.current) return;
      const aiMsg = { id: 'a' + Date.now(), isUser: false, isAI: true, ...reply };
      const finalMsgs = [userMsg, aiMsg];
      setMsgs(finalMsgs);
      saveConvo(id, situationText.slice(0, 48), 'refletir', finalMsgs);
    } catch (err) {
      console.error('handleGoReflect failed:', err);
      if (requestId !== requestIdRef.current) return;
      setMsgs([userMsg, { id: 'a' + Date.now(), isUser: false, isAI: true, ...ERROR_MSG }]);
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
        scrollToBottom();
      }
    }
  };

  // ── Suggested-mode: jump from /reflect to a Dúvida thread seeded with the question ──
  const handleGoDuvida = async (questionText) => {
    if (!questionText) return;
    switchMode('duvida');
    const userMsg = { id: 'u' + Date.now(), isUser: true, isAI: false, text: questionText };
    setMsgs([userMsg]); setLoading(true);
    const id = 'c' + Date.now();
    setConvoId(id);
    saveConvo(id, questionText.slice(0, 48), 'duvida', [userMsg]);
    scrollToBottom();
    const requestId = ++requestIdRef.current;
    try {
      const reply = await chatMessage(questionText, [], null, 'tirar_duvida');
      if (requestId !== requestIdRef.current) return;
      const aiMsg = { id: 'a' + Date.now(), isUser: false, isAI: true, ...reply };
      const finalMsgs = [userMsg, aiMsg];
      setMsgs(finalMsgs);
      saveConvo(id, questionText.slice(0, 48), 'duvida', finalMsgs);
    } catch (err) {
      console.error('handleGoDuvida failed:', err);
      if (requestId !== requestIdRef.current) return;
      setMsgs([userMsg, { id: 'a' + Date.now(), isUser: false, isAI: true, ...ERROR_MSG }]);
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
        scrollToBottom();
      }
    }
  };

  const markFromCache = (msgs) => msgs.map(m => m.isAI ? { ...m, fromCache: true } : m);

  // ── Load a saved conversation from the sidebar into the right mode/sub-screen ──
  const handleLoadConvo = async (c) => {
    threadEpochRef.current += 1; // replaces a thread — drop stale async replies
    setConvoId(c.id);
    const msgs = markFromCache(c.msgs);
    // `sub` is stored explicitly on conversations saved after this field was
    // added; fall back to the old id-prefix convention for older entries
    // already sitting in a user's localStorage.
    const sub = c.sub || (c.id.startsWith('trilha_') ? 'guided' : c.id.startsWith('explorar_') ? 'explorar' : null);
    if (c.mode === 'refletir') {
      setMode('refletir'); setRefletirSub('chat'); setMsgs(msgs);
    } else if (c.mode === 'estudar' && sub === 'guided') {
      setMode('estudar'); setEstudarSub('guided');
      const trilhaId = c.id.slice('trilha_'.length);
      const trilhaDetail = await getPath(trilhaId).catch((err) => {
        console.error('handleLoadConvo failed to fetch trilha detail:', err);
        return null;
      });
      setActiveTrilha(trilhaDetail);
      const tutorSteps = msgs.filter(m => typeof m.id === 'string' && m.id.startsWith('tutor_'));
      setGuidedStep(Math.max(0, tutorSteps.length - 1));
      setGuidedMsgs(msgs);
    } else if (c.mode === 'estudar' && sub === 'explorar') {
      setMode('estudar'); setEstudarSub('explorar');
      const meta = { id: c.id, title: c.title };
      setExplorarConvoMeta(meta);
      explorarConvoMetaRef.current = meta;
      setExplorarMsgs(msgs);
    } else {
      requestIdRef.current += 1;
      setMode('duvida');
      setMsgs(msgs);
      setInput('');
      setLoading(false);
    }
  };

  // ── Trilha progress (for the Estudar picker) ──────────────────────────────
  // Derive, per started trilha, how far the user got, from the cached guided
  // conversation. `step` counts the `tutor_` step messages already presented
  // (same reconstruction handleLoadConvo uses); the picker pairs it with the
  // trilha's total step_count. Only trilhas with a saved conversation appear.
  const trilhaProgress = useMemo(() => {
    const out = {};
    for (const c of conversations) {
      if (typeof c.id !== 'string' || !c.id.startsWith('trilha_')) continue;
      const trilhaId = c.id.slice('trilha_'.length);
      const step = (c.msgs || []).filter(
        m => typeof m.id === 'string' && m.id.startsWith('tutor_')
      ).length;
      out[trilhaId] = { step };
    }
    return out;
  }, [conversations]);

  // Resume a started trilha from cache — no LLM call (contrast with startTrilha).
  const handleResumeTrilha = (tr) => {
    const convo = conversations.find(c => c.id === 'trilha_' + tr.id);
    if (convo) handleLoadConvo(convo);
    else startTrilha(tr); // no cache (shouldn't happen from an in-progress card)
  };

  // ── Redirect to dúvida with context ──────────────────────────────────────
  const redirectToDuvida = (obraLabel) => {
    const ctx = `Contexto: estou estudando "${obraLabel}". `;
    switchMode('duvida');
    setTimeout(() => setInput(ctx), 50);
  };

  // ── Refletir submit ──────────────────────────────────────────────────────
  const handleReflectSubmit = (text) => {
    setRefletirSub('chat');
    sendText(text);
  };

  // ── Daily trecho (evangelho) ──────────────────────────────────────────────
  const handleStudyTrecho = async () => {
    if (!evangelhoData) return;
    switchMode('duvida');
    const epoch = threadEpochRef.current; // after switchMode's bump
    const { source, content } = evangelhoData;
    const userMsg = { id: 'u' + Date.now(), isUser: true, isAI: false, text: 'Estudo diário de hoje' };
    const id = 'trecho_' + Date.now();
    setConvoId(id);
    setMsgs([userMsg]); setLoading(true); scrollToBottom();

    let reply;
    try {
      if (source.item_number) {
        reply = await studyItem(source.book, source.item_number, source.chapter || null);
      } else {
        reply = await chatMessage(`Explique este trecho do Evangelho: "${content.slice(0, 300)}"`);
      }
    } catch (err) {
      console.error('handleStudyTrecho failed:', err);
      reply = { hasDaObra: false, obra: null, ia: 'Não foi possível carregar o estudo diário.' };
    } finally {
      setLoading(false);
    }

    // User may have switched threads while /study ran — don't clobber the new one.
    if (epoch !== threadEpochRef.current) return;
    const finalMsgs = [userMsg, { id: 'a' + Date.now(), isUser: false, isAI: true, isTrecho: true, ...reply }];
    setMsgs(finalMsgs);
    saveConvo(id, 'Trecho do dia', 'duvida', finalMsgs);
    scrollToBottom();
  };

  // ── Reminder notification click ───────────────────────────────────────────
  const handleNotificationClick = useCallback(() => {
    switchMode('duvida');
    handleStudyTrecho();
  }, [switchMode, handleStudyTrecho]);

  useReminder({
    enabled: reminderOn, time: reminderTime, permission: notifPerm,
    onNotificationClick: handleNotificationClick,
  });

  // ── Notification permission ───────────────────────────────────────────────
  const requestNotif = async () => {
    if (typeof Notification === 'undefined') return;
    const perm = await Notification.requestPermission();
    setNotifPerm(perm);
  };

  // ── Render ────────────────────────────────────────────────────────────────
  const isHome = mode === null;
  const isEstudar = mode === 'estudar';
  const isRefletir = mode === 'refletir';
  // `!isHome` matters: without it the old empty state renders underneath the
  // home launcher, and the user meets two different launchers.
  const isEmpty = !isHome && msgs.length === 0 && !loading && !isEstudar;

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

      {/* Onboarding */}
      {!onboarded && (
        <Onboarding onFinish={() => setOnboarded(true)} />
      )}

      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>

        {/* Sidebar (desktop) */}
        {!isMobile && (
          <div style={{ width: 300, flexShrink: 0, display: 'flex' }}>
            <Sidebar
              onNewConvo={newConvo}
              onStudyTrecho={handleStudyTrecho}
              onTutorial={() => setOnboarded(false)}
              conversations={conversations}
              onLoadConvo={handleLoadConvo}
              onDeleteConvo={handleDeleteConvo}
              onToggleConvoFavorite={toggleConvoFavorite}
              evangelhoData={evangelhoData}
            />
          </div>
        )}

        {/* Mobile drawer */}
        {isMobile && drawerOpen && (
          <>
            <style>{`@keyframes slideInDrawer { from { transform: translateX(-100%); } to { transform: translateX(0); } }`}</style>
            <div
              style={{ position: 'fixed', inset: 0, zIndex: 80, background: 'rgba(0,0,0,.45)' }}
              onClick={() => setDrawerOpen(false)}
            />
            <div style={{
              position: 'fixed', top: 0, left: 0, bottom: 0, zIndex: 81,
              width: 'min(300px, 85vw)', display: 'flex',
              animation: 'slideInDrawer .22s cubic-bezier(.25,.46,.45,.94)',
              boxShadow: '4px 0 24px rgba(0,0,0,.3)',
            }}>
              <Sidebar
                onNewConvo={() => { newConvo(); setDrawerOpen(false); }}
                onStudyTrecho={() => { handleStudyTrecho(); setDrawerOpen(false); }}
                onTutorial={() => { setOnboarded(false); setDrawerOpen(false); }}
                conversations={conversations}
                onLoadConvo={(c) => { handleLoadConvo(c); setDrawerOpen(false); }}
                onDeleteConvo={handleDeleteConvo}
                onToggleConvoFavorite={toggleConvoFavorite}
                evangelhoData={evangelhoData}
                onClose={() => setDrawerOpen(false)}
                isMobile
              />
            </div>
          </>
        )}

        {/* Main area */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, background: theme.chatBg }}>

          {/* Top bar */}
          <TopBar
            mode={mode} theme={theme}
            onOpenSettings={() => setShowSettings(true)}
            onOpenDrawer={isMobile ? () => setDrawerOpen(true) : undefined}
            isMobile={isMobile}
          />

          {/* Content */}
          {isHome && (
            <HomeLauncher
              onPick={switchMode}
              theme={theme}
              evangelhoData={evangelhoData}
              onStudyTrecho={handleStudyTrecho}
              isMobile={isMobile}
            />
          )}

          {isEstudar && estudarSub === 'picker' && (
            <EstudarPicker
              theme={theme}
              onStartTrilha={startTrilha}
              onResumeTrilha={handleResumeTrilha}
              onExplorar={() => { setEstudarSub('explorar'); setExplorarMsgs([]); }}
              onVerIntro={() => setEstudarSub('intro')}
              paths={paths}
              pathsLoading={pathsLoading}
              completedTrilhas={completedTrilhas}
              trilhaProgress={trilhaProgress}
            />
          )}

          {isEstudar && estudarSub === 'intro' && (
            <IntroObras
              theme={theme}
              onBack={() => setEstudarSub('picker')}
            />
          )}

          {isEstudar && estudarSub === 'guided' && (
            <GuidedStudy
              trilha={activeTrilha}
              currentStep={guidedStep}
              messages={guidedMsgs}
              loading={guidedLoading}
              theme={theme}
              fontSize={msgFontSize}
              onNext={handleGuidedNext}
              onBack={() => setEstudarSub('picker')}
              onAskDuvida={handleGuidedDuvida}
              quickActions={QUICK_ACTIONS}
              onQuickAction={handleGuidedQuickAction}
            />
          )}

          {isEstudar && estudarSub === 'explorar' && (
            <ExplorarObras
              theme={theme}
              onBack={() => setEstudarSub('picker')}
              onRedirectDuvida={redirectToDuvida}
              onAskTopic={handleAskTopic}
              onSendMessage={handleExplorarChat}
              messages={explorarMsgs}
              loading={explorarLoad}
              fontSize={msgFontSize}
              quickActions={QUICK_ACTIONS}
              onQuickAction={handleExplorarQuickAction}
              onBookChange={() => { threadEpochRef.current += 1; setExplorarMsgs([]); setExplorarConvoMeta(null); explorarConvoMetaRef.current = null; }}
              onAskDuvida={handleExplorarDuvida}
            />
          )}

          {isRefletir && refletirSub === 'picker' && (
            <RefletirPicker theme={theme} onSubmit={handleReflectSubmit} />
          )}

          {!isHome && !isEstudar && !(isRefletir && refletirSub === 'picker') && (
            <>
              {/* Chat messages */}
              <div ref={msgsRef} style={{
                flex: 1, overflowY: 'auto', minHeight: 0,
                padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 14,
              }}>
                {isEmpty && (
                  <div style={{
                    flex: 1, display: 'flex', flexDirection: 'column',
                    alignItems: 'center', justifyContent: 'center',
                    textAlign: 'center', padding: '40px 16px',
                  }}>
                    <div style={{
                      width: 52, height: 52, borderRadius: '50%',
                      background: 'rgba(107,155,184,.12)',
                      border: '1px solid rgba(107,155,184,.2)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      marginBottom: 16, fontSize: 24,
                    }}>
                      {MODES.find(m => m.id === mode)?.icon || '💬'}
                    </div>
                    <div style={{
                      fontFamily: "'Crimson Pro', serif",
                      fontSize: 19, fontWeight: 600, color: theme.text, marginBottom: 6,
                    }}>
                      {MODES.find(m => m.id === mode)?.label}
                    </div>
                    <div style={{
                      fontSize: 13.5, color: theme.text, opacity: .85, maxWidth: 340, lineHeight: 1.5,
                    }}>
                      {MODES.find(m => m.id === mode)?.desc}
                    </div>

                    {/* Starter questions. These came back after the old empty
                        state was retired: that screen mixed TWO things, and only
                        one was redundant. The mode cards duplicated the home
                        launcher and are gone for good; these chips were the only
                        one-tap way into a first question, and losing them cost
                        discovery — worst on mobile, where typing is expensive.
                        Chips, not cards: the visual weight is what made the old
                        screen feel cluttered. */}
                    {mode === 'duvida' && (
                      <div style={{
                        display: 'flex', flexWrap: 'wrap', justifyContent: 'center',
                        gap: 8, marginTop: 26, maxWidth: 460,
                      }}>
                        {SUGGESTIONS.map(sug => (
                          <button
                            key={sug.label}
                            onClick={() => sendText(sug.label)}
                            style={{
                              background: 'transparent',
                              border: `1px solid ${theme.cardBorder}`,
                              borderRadius: 999, padding: '7px 13px',
                              cursor: 'pointer', font: 'inherit',
                              fontSize: 12.5, color: theme.text,
                              display: 'flex', alignItems: 'center', gap: 6,
                              lineHeight: 1.35, textAlign: 'left',
                            }}
                          >
                            <span aria-hidden="true">{sug.icon}</span>
                            {sug.label}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {msgs.map((msg, idx) => (
                  msg.isUser
                    ? <UserBubble key={msg.id} text={msg.text} />
                    : <AIMessage key={msg.id} msg={msg} theme={theme} fontSize={msgFontSize}
                        onShare={msg.isTrecho ? () => setShareMsg(msg) : undefined}
                        isMobile={isMobile}
                        showQuickActions={false}
                        quickActions={QUICK_ACTIONS.filter(
                          qa => qa.label !== '📚 Relacionados' || msg.relatedItems?.length > 0
                        )}
                        onQuickAction={(label) => handleQuickAction(label, msg)}
                        onReflectionQuestionClick={handleReflectionQuestionClick}
                        suggestedQuestions={
                          idx === msgs.length - 1 && !msg.isReflection && !loading
                            ? (msg.suggestedQuestions || [])
                            : []
                        }
                        onSuggestedQuestionClick={(q) => sendText(q)}
                        footerAction={(() => {
                          const srcMsg = msgs.slice(0, idx).reverse().find(m => m.isUser)?.text;
                          if (msg.suggestedMode === 'estudar_obra') {
                            const studyTarget = resolveStudyTarget(msg);
                            return studyTarget ? {
                              label: `📖 Estudar ${formatItemRef(studyTarget.book, studyTarget.item_number)} na íntegra`,
                              onClick: () => handleGoStudyItem(studyTarget),
                            } : null;
                          }
                          if (msg.suggestedMode === 'refletir') {
                            return srcMsg ? {
                              label: '🪞 Refletir sobre esta situação',
                              color: '#C8856A',
                              onClick: () => handleGoReflect(srcMsg),
                            } : null;
                          }
                          if (msg.suggestedMode === 'tirar_duvida') {
                            return srcMsg ? {
                              label: '💬 Dialogar sobre isto',
                              onClick: () => handleGoDuvida(srcMsg),
                            } : null;
                          }
                          return null;
                        })()}
                      />
                ))}
                {loading && <LoadingDots theme={theme} />}
              </div>

              {/* Input — hidden in Refletir mode: that flow is fully button-driven */}
              {!isRefletir && (
                <InputBar
                  value={input}
                  onChange={setInput}
                  onSend={handleSend}
                  placeholder={(isMobile ? MODE_PLACEHOLDER_MOBILE : MODE_PLACEHOLDER)[mode] || ''}
                  footerHint="IA treinada no Pentateuco Espírita · Respostas sempre referenciadas em Kardec · Enter para enviar"
                  theme={theme}
                  loading={loading}
                  isMobile={isMobile}
                />
              )}
            </>
          )}
        </div>
      </div>

      {/* Mobile bottom nav */}
      {isMobile && <MobileBottomNav mode={mode} onChange={switchMode} onStudyTrecho={handleStudyTrecho} />}

      {/* Modals */}
      <SettingsPanel
        open={showSettings} onClose={() => setShowSettings(false)}
        darkMode={darkMode} onToggleDark={toggleDark}
        fontSize={fontSize} onFontSize={setFontSize}
        reminderOn={reminderOn} onToggleReminder={() => setReminderOn(r => !r)}
        reminderTime={reminderTime} onReminderTime={setReminderTime}
        notifPermission={notifPerm} onRequestNotif={requestNotif}
        theme={theme}
      />
      {shareMsg && <ShareModal msg={shareMsg} theme={theme} onClose={() => setShareMsg(null)} />}
      {relatedModal && (
        <RelatedItemsModal
          modal={relatedModal}
          theme={theme}
          onClose={() => setRelatedModal(null)}
          onSelectItem={async (item) => {
            const { appendMsg, setLoad } = relatedModal;
            setRelatedModal(null);
            setLoad(true);
            scrollToBottom();
            try {
              const reply = await studyItem(item.book, item.item_number, item.chapter || null);
              appendMsg({ id: 'a' + Date.now(), isUser: false, isAI: true, ...reply });
            } catch (err) {
              console.error('RelatedItemsModal onSelectItem failed:', err);
              appendMsg({
                id: 'a' + Date.now(), isUser: false, isAI: true,
                hasDaObra: false, obra: null, ia: 'Não foi possível carregar este item.',
              });
            } finally {
              setLoad(false);
              scrollToBottom();
            }
          }}
        />
      )}
      <TrilhaCompleteModal
        modal={trilhaCompleteModal}
        theme={theme}
        onShare={() => {
          setShareMsg(trilhaCompleteModal.lastMsg);
          setTrilhaCompleteModal(null);
          setEstudarSub('picker');
        }}
        onClose={() => {
          setTrilhaCompleteModal(null);
          setEstudarSub('picker');
        }}
      />
    </div>
  );
}

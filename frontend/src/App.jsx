import React, { useState, useRef, useEffect, useCallback } from 'react';
import Sidebar from './components/layout/Sidebar';
import TopBar from './components/layout/TopBar';
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
import { lightTheme } from './constants/theme';
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

const SUGGESTIONS = [
  { icon: '📖', label: 'O que é o Espiritismo?' },
  { icon: '💬', label: 'Qual a diferença entre alma, perispírito e espírito?' },
  { icon: '🔄', label: 'O que é a reencarnação?' },
  { icon: '🪞', label: 'Como posso ter mais paz no dia a dia?' },
];

const ERROR_MSG = {
  hasDaObra: false, obra: null,
  ia: 'Não foi possível obter uma resposta. Verifique sua conexão e tente novamente.',
};

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
  const [mode,          setMode]         = useState('duvida');
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

  const scrollToBottom = () => {
    let ticks = 0;
    const interval = setInterval(() => {
      if (msgsRef.current) msgsRef.current.scrollTop = msgsRef.current.scrollHeight;
      ticks += 1;
      if (ticks >= 20) clearInterval(interval); // ~2s at 100ms
    }, 100);
  };

  // ── Font size helper ─────────────────────────────────────────────────────
  const msgFontSize = { small: '14px', medium: '15px', large: '17px' }[fontSize] || '15px';

  // ── Mode switching ───────────────────────────────────────────────────────
  const switchMode = (m) => {
    requestIdRef.current += 1; // invalidate any in-flight sendText for the old mode
    setMode(m); setMsgs([]); setLoading(false); setInput(''); setConvoId(null);
    if (m === 'estudar') setEstudarSub('picker');
    if (m === 'refletir') setRefletirSub('picker');
  };

  // ── Main chat send (dúvida + refletir) ───────────────────────────────────
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
        reply = await reflectSituation(txt);
      } else {
        const history = msgs.map(m => ({
          role: m.isUser ? 'user' : 'assistant',
          content: m.isUser ? m.text : (m.ia || ''),
        }));
        reply = await chatMessage(txt, history);
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
      const reply = await reflectSituation(question, history);
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

    if (label === '📄 Ler original') {
      if (msg.obra?.quote) {
        appendMsg({
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
    appendMsg({ id: 'u' + Date.now(), isUser: true, isAI: false, text: userText });
    setLoad(true);
    scrollToBottom();
    try {
      const reply = label === '🪞 Reflexão'
        ? await reflectSituation(snippet)
        : await chatMessage(`Explique de forma mais simples: "${snippet}"`);
      appendMsg({ id: 'a' + Date.now(), isUser: false, isAI: true, ...reply });
    } catch (err) {
      console.error('runQuickAction failed:', err);
      appendMsg({ id: 'a' + Date.now(), isUser: false, isAI: true, ...ERROR_MSG });
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
  const askDuvida = async (text, appendMsg, setLoad) => {
    if (!text.trim()) return;
    appendMsg({ id: 'u' + Date.now(), isUser: true, isAI: false, text });
    setLoad(true);
    scrollToBottom();
    try {
      const reply = await chatMessage(text);
      appendMsg({ id: 'a' + Date.now(), isUser: false, isAI: true, ...reply });
    } catch (err) {
      console.error('askDuvida failed:', err);
      appendMsg({ id: 'a' + Date.now(), isUser: false, isAI: true, ...ERROR_MSG });
    } finally {
      setLoad(false);
      scrollToBottom();
    }
  };
  const handleGuidedDuvida = (text) => askDuvida(text, m => setGuidedMsgs(prev => [...prev, m]), setGuidedLoading);
  const handleExplorarDuvida = (text) => askDuvida(text, m => {
    setExplorarMsgs(prev => {
      const updated = [...prev, m];
      if (explorarConvoMetaRef.current) saveConvo(explorarConvoMetaRef.current.id, explorarConvoMetaRef.current.title, 'estudar', updated);
      return updated;
    });
  }, setExplorarLoad);

  // ── Guided study ──────────────────────────────────────────────────────────
  const startTrilha = async (pathSummary) => {
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
    saveConvo('trilha_' + trilha.id, trilha.title, 'estudar', updatedMsgs);
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
        reply = await chatMessage(bookName ? `Contexto: ${bookName}. ${query}` : query);
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
    saveConvo(convoId2, title, 'estudar', [userMsg, aiMsg]);
    setExplorarMsgs([userMsg, aiMsg]);
    scrollToBottom();
  };

  // ── Load a saved conversation from the sidebar into the right mode/sub-screen ──
  const handleLoadConvo = async (c) => {
    setConvoId(c.id);
    if (c.mode === 'refletir') {
      setMode('refletir'); setRefletirSub('chat'); setMsgs(c.msgs);
    } else if (c.mode === 'estudar' && c.id.startsWith('trilha_')) {
      setMode('estudar'); setEstudarSub('guided');
      const trilhaId = c.id.slice('trilha_'.length);
      const trilhaDetail = await getPath(trilhaId).catch((err) => {
        console.error('handleLoadConvo failed to fetch trilha detail:', err);
        return null;
      });
      setActiveTrilha(trilhaDetail);
      const tutorSteps = c.msgs.filter(m => typeof m.id === 'string' && m.id.startsWith('tutor_'));
      setGuidedStep(Math.max(0, tutorSteps.length - 1));
      setGuidedMsgs(c.msgs);
    } else if (c.mode === 'estudar' && c.id.startsWith('explorar_')) {
      setMode('estudar'); setEstudarSub('explorar');
      const meta = { id: c.id, title: c.title };
      setExplorarConvoMeta(meta);
      explorarConvoMetaRef.current = meta;
      setExplorarMsgs(c.msgs);
    } else {
      setMode(c.mode); setMsgs(c.msgs);
    }
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
    const { source, content } = evangelhoData;
    const userMsg = { id: 'u' + Date.now(), isUser: true, isAI: false, text: 'Estudo diário de hoje' };
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

    setMsgs([userMsg, { id: 'a' + Date.now(), isUser: false, isAI: true, ...reply }]);
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
  const isEstudar = mode === 'estudar';
  const isRefletir = mode === 'refletir';
  const isEmpty = msgs.length === 0 && !loading && !isEstudar;

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

      {/* Onboarding */}
      {!onboarded && (
        <Onboarding onFinish={() => setOnboarded(true)} />
      )}

      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>

        {/* Sidebar (desktop) */}
        {!isMobile && (
          <Sidebar
            mode={mode}
            onModeChange={switchMode}
            onStudyTrecho={handleStudyTrecho}
            onTutorial={() => setOnboarded(false)}
            conversations={conversations}
            onLoadConvo={handleLoadConvo}
            onDeleteConvo={deleteConvo}
            onToggleConvoFavorite={toggleConvoFavorite}
            evangelhoData={evangelhoData}
          />
        )}

        {/* Mobile drawer */}
        {isMobile && drawerOpen && (
          <>
            <div
              style={{ position: 'fixed', inset: 0, zIndex: 80, background: 'rgba(0,0,0,.5)' }}
              onClick={() => setDrawerOpen(false)}
            />
            <div style={{ position: 'fixed', top: 0, left: 0, bottom: 0, zIndex: 81, width: 300 }}>
              <Sidebar
                mode={mode}
                onModeChange={(m) => { switchMode(m); setDrawerOpen(false); }}
                onStudyTrecho={() => { handleStudyTrecho(); setDrawerOpen(false); }}
                onTutorial={() => { setOnboarded(false); setDrawerOpen(false); }}
                conversations={conversations}
                onLoadConvo={(c) => { handleLoadConvo(c); setDrawerOpen(false); }}
                onDeleteConvo={deleteConvo}
                onToggleConvoFavorite={toggleConvoFavorite}
                evangelhoData={evangelhoData}
                onClose={() => setDrawerOpen(false)}
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
          />

          {/* Content */}
          {isEstudar && estudarSub === 'picker' && (
            <EstudarPicker
              theme={theme}
              onStartTrilha={startTrilha}
              onExplorar={() => { setEstudarSub('explorar'); setExplorarMsgs([]); }}
              onVerIntro={() => setEstudarSub('intro')}
              paths={paths}
              pathsLoading={pathsLoading}
              completedTrilhas={completedTrilhas}
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
              onShare={setShareMsg}
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
              messages={explorarMsgs}
              loading={explorarLoad}
              onShare={setShareMsg}
              fontSize={msgFontSize}
              quickActions={QUICK_ACTIONS}
              onQuickAction={handleExplorarQuickAction}
              onBookChange={() => { setExplorarMsgs([]); setExplorarConvoMeta(null); explorarConvoMetaRef.current = null; }}
              onAskDuvida={handleExplorarDuvida}
            />
          )}

          {isRefletir && refletirSub === 'picker' && (
            <RefletirPicker theme={theme} onSubmit={handleReflectSubmit} />
          )}

          {!isEstudar && !(isRefletir && refletirSub === 'picker') && (
            <>
              {/* Chat messages */}
              <div ref={msgsRef} style={{
                flex: 1, overflowY: 'auto', minHeight: 0,
                padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 14,
              }}>
                {isEmpty && (
                  <div style={{
                    flex: 1, display: 'flex', flexDirection: 'column',
                    alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '40px 16px',
                  }}>
                    <div style={{
                      width: 52, height: 52, borderRadius: '50%',
                      background: 'rgba(107,155,184,.12)', border: '1px solid rgba(107,155,184,.2)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16,
                    }}>
                      <svg width={22} height={22} viewBox="0 0 24 24" fill="none"
                        stroke="#6B9BB8" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
                        <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
                      </svg>
                    </div>
                    <div style={{ fontFamily: "'Crimson Pro', serif", fontSize: 22, fontWeight: 600, color: theme.text, marginBottom: 8 }}>
                      Em que posso ajudar?
                    </div>
                    <div style={{ fontSize: 14, color: theme.subtext, maxWidth: 300, lineHeight: 1.72, marginBottom: 22 }}>
                      Escolha uma sugestão ou digite sua pergunta.
                    </div>
                    <button onClick={() => switchMode('estudar')} style={{
                      background: 'rgba(107,155,184,.08)', border: '1px solid rgba(107,155,184,.3)',
                      borderRadius: 10, padding: '14px 16px', cursor: 'pointer',
                      textAlign: 'left', display: 'flex', alignItems: 'center', gap: 10,
                      maxWidth: 360, width: '100%', marginBottom: 14,
                    }}>
                      <span style={{ fontSize: 20 }}>📚</span>
                      <div>
                        <div style={{ fontSize: 13.5, color: theme.text, fontWeight: 600 }}>Estudar uma Obra</div>
                        <div style={{ fontSize: 12, color: theme.subtext, marginTop: 1 }}>Trilhas guiadas e livre exploração pelas 5 obras</div>
                      </div>
                    </button>
                    <button onClick={() => switchMode('refletir')} style={{
                      background: 'rgba(200,133,106,.08)', border: '1px solid rgba(200,133,106,.3)',
                      borderRadius: 10, padding: '14px 16px', cursor: 'pointer',
                      textAlign: 'left', display: 'flex', alignItems: 'center', gap: 10,
                      maxWidth: 360, width: '100%', marginBottom: 14,
                    }}>
                      <span style={{ fontSize: 20 }}>🪞</span>
                      <div>
                        <div style={{ fontSize: 13.5, color: theme.text, fontWeight: 600 }}>Refletir sobre uma Situação</div>
                        <div style={{ fontSize: 12, color: theme.subtext, marginTop: 1 }}>Veja momentos da sua vida pela lente da doutrina espírita</div>
                      </div>
                    </button>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, maxWidth: 360 }}>
                      {SUGGESTIONS.map(s => (
                        <button key={s.label} onClick={() => sendText(s.label)} style={{
                          background: theme.cardBg, border: `1px solid ${theme.cardBorder}`,
                          borderRadius: 10, padding: '12px 14px', cursor: 'pointer',
                          textAlign: 'left', display: 'flex', flexDirection: 'column', gap: 5,
                        }}>
                          <span style={{ fontSize: 16, lineHeight: 1 }}>{s.icon}</span>
                          <span style={{ fontSize: 13, color: theme.text, fontWeight: 500, lineHeight: 1.45 }}>{s.label}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {msgs.map(msg => (
                  msg.isUser
                    ? <UserBubble key={msg.id} text={msg.text} />
                    : <AIMessage key={msg.id} msg={msg} theme={theme} fontSize={msgFontSize}
                        onShare={() => setShareMsg(msg)}
                        showQuickActions={false}
                        quickActions={QUICK_ACTIONS.filter(
                          qa => qa.label !== '📚 Relacionados' || msg.relatedItems?.length > 0
                        )}
                        onQuickAction={(label) => handleQuickAction(label, msg)}
                        onReflectionQuestionClick={handleReflectionQuestionClick}
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
                  placeholder={MODE_PLACEHOLDER[mode] || ''}
                  footerHint="IA treinada no Pentateuco Espírita · Respostas sempre referenciadas em Kardec · Enter para enviar"
                  theme={theme}
                  loading={loading}
                />
              )}
            </>
          )}
        </div>
      </div>

      {/* Mobile bottom nav */}
      {isMobile && <MobileBottomNav mode={mode} onChange={switchMode} />}

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

import React, { useState, useRef, useEffect } from 'react';
import Sidebar from './components/layout/Sidebar';
import TopBar from './components/layout/TopBar';
import MobileBottomNav from './components/layout/MobileBottomNav';
import Onboarding from './components/modals/Onboarding';
import SettingsPanel from './components/modals/SettingsPanel';
import ShareModal from './components/modals/ShareModal';
import EstudarPicker from './components/modes/EstudarPicker';
import GuidedStudy from './components/modes/GuidedStudy';
import ExplorarObras from './components/modes/ExplorarObras';
import UserBubble from './components/chat/UserBubble';
import AIMessage from './components/chat/AIMessage';
import LoadingDots from './components/chat/LoadingDots';
import InputBar from './components/chat/InputBar';
import { useTheme } from './hooks/useTheme';
import { useStorage } from './hooks/useStorage';
import { useConversations } from './hooks/useConversations';
import { useFavorites } from './hooks/useFavorites';
import { useReminder } from './hooks/useReminder';
import { lightTheme } from './constants/theme';
import {
  chatMessage, studyItem, reflectSituation,
  getEvangelho, getPaths, getPath,
  BOOK_NAME_MAP, parseItemRef,
} from './services/api';

const QUICK_ACTIONS = [
  { label: '📄 Ler original' }, { label: '💡 Explicar simples' },
  { label: '🪞 Reflexão' },     { label: '🏛 Contexto histórico' },
  { label: '📚 Relacionados' },  { label: '🔖 Salvar' },
];

const MODE_PLACEHOLDER = {
  estudar:  'Ex: Explique a questão 132 do Livro dos Espíritos…',
  duvida:   'Ex: O que Kardec fala sobre reencarnação?',
  refletir: 'Ex: Estou passando por um conflito familiar…',
};

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
  const [reminderOn,   setReminderOn]   = useStorage('dialogando_reminder_on', false);
  const [reminderTime, setReminderTime] = useStorage('dialogando_reminder_time', '08:00');
  const [notifPerm,    setNotifPerm]    = useState(() => typeof Notification !== 'undefined' ? Notification.permission : 'default');
  const { conversations, saveConvo } = useConversations();
  const { favorites, toggleFavorite, isFavorite } = useFavorites();
  useReminder({ enabled: reminderOn, time: reminderTime, permission: notifPerm });

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
  const [activeTrilha,  setActiveTrilha] = useState(null);
  const [guidedStep,    setGuidedStep]   = useState(0);
  const [guidedMsgs,    setGuidedMsgs]   = useState([]);
  const [guidedLoading, setGuidedLoading]= useState(false);
  const [guidedDone,    setGuidedDone]   = useState(false);
  const [explorarMsgs,  setExplorarMsgs] = useState([]);
  const [explorarLoad,  setExplorarLoad] = useState(false);
  const [showSettings,  setShowSettings] = useState(false);
  const [shareMsg,      setShareMsg]     = useState(null);
  const [convoId,       setConvoId]      = useState(null);
  const [isMobile,      setIsMobile]     = useState(() => window.innerWidth < 768);
  const [drawerOpen,    setDrawerOpen]   = useState(false);
  const msgsRef = useRef(null);

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
    setTimeout(() => { if (msgsRef.current) msgsRef.current.scrollTop = msgsRef.current.scrollHeight; }, 60);
  };

  // ── Font size helper ─────────────────────────────────────────────────────
  const msgFontSize = { small: '12px', medium: '13px', large: '15.5px' }[fontSize] || '13px';

  // ── Mode switching ───────────────────────────────────────────────────────
  const switchMode = (m) => {
    setMode(m); setMsgs([]); setLoading(false); setInput(''); setConvoId(null);
    if (m === 'estudar') setEstudarSub('picker');
  };

  // ── Main chat send (dúvida + refletir) ───────────────────────────────────
  const handleSend = async () => {
    const txt = input.trim();
    if (!txt) return;
    const userMsg = { id: 'u' + Date.now(), isUser: true, isAI: false, text: txt };
    const newMsgs = [...msgs, userMsg];
    setMsgs(newMsgs); setInput(''); setLoading(true);
    const id = convoId || ('c' + Date.now());
    setConvoId(id);
    saveConvo(id, txt.slice(0, 48), mode, newMsgs);
    scrollToBottom();

    try {
      let reply;
      if (mode === 'refletir') {
        reply = await reflectSituation(txt);
      } else {
        const history = msgs.map(m => ({
          role: m.isUser ? 'user' : 'assistant',
          content: m.isUser ? m.text : (m.ia || ''),
        }));
        reply = await chatMessage(txt, history);
      }
      const aiMsg = { id: 'a' + Date.now(), isUser: false, isAI: true, ...reply };
      const finalMsgs = [...newMsgs, aiMsg];
      setMsgs(finalMsgs);
      saveConvo(id, txt.slice(0, 48), mode, finalMsgs);
    } catch {
      setMsgs([...newMsgs, { id: 'a' + Date.now(), isUser: false, isAI: true, ...ERROR_MSG }]);
    } finally {
      setLoading(false);
      scrollToBottom();
    }
  };

  // ── Guided study ──────────────────────────────────────────────────────────
  const startTrilha = async (pathSummary) => {
    setEstudarSub('guided');
    setGuidedStep(0); setGuidedMsgs([]); setGuidedDone(false); setGuidedLoading(true);
    let pathDetail;
    try {
      pathDetail = await getPath(pathSummary.id);
    } catch {
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
        obra: reply.obra ? { ...reply.obra, title: `${step.book} — ${step.label}` } : null,
      };
    } catch {
      tutorMsg = {
        id: 'tutor_' + stepIdx,
        isUser: false, isAI: true, hasDaObra: false, obra: null,
        ia: `Não foi possível carregar "${step.label}". Tente novamente.`,
      };
    }
    setGuidedMsgs([...existingMsgs, tutorMsg]);
    setGuidedLoading(false);
    scrollToBottom();
  };

  const handleGuidedNext = async () => {
    const next = guidedStep + 1;
    if (next >= activeTrilha.steps.length) { setGuidedDone(true); return; }
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
      if (err.status === 404) {
        try { reply = await chatMessage(query); }
        catch { reply = { hasDaObra: false, obra: null, ia: 'Não foi possível obter uma resposta.' }; }
      } else {
        reply = { hasDaObra: false, obra: null, ia: 'Não foi possível obter uma resposta.' };
      }
    } finally {
      setExplorarLoad(false);
    }

    const aiMsg = { id: 'ea' + Date.now(), isUser: false, isAI: true, ...reply };
    setExplorarMsgs([userMsg, aiMsg]);
    scrollToBottom();
  };

  // ── Redirect to dúvida with context ──────────────────────────────────────
  const redirectToDuvida = (obraLabel) => {
    const ctx = `Contexto: estou estudando "${obraLabel}". `;
    switchMode('duvida');
    setTimeout(() => setInput(ctx), 50);
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
        reply = await studyItem(source.book, source.item_number);
      } else {
        reply = await chatMessage(`Explique este trecho do Evangelho: "${content.slice(0, 300)}"`);
      }
    } catch {
      reply = { hasDaObra: false, obra: null, ia: 'Não foi possível carregar o estudo diário.' };
    } finally {
      setLoading(false);
    }

    setMsgs([userMsg, { id: 'a' + Date.now(), isUser: false, isAI: true, ...reply }]);
    scrollToBottom();
  };

  // ── Notification permission ───────────────────────────────────────────────
  const requestNotif = async () => {
    if (typeof Notification === 'undefined') return;
    const perm = await Notification.requestPermission();
    setNotifPerm(perm);
  };

  // ── Render ────────────────────────────────────────────────────────────────
  const isEstudar = mode === 'estudar';
  const isEmpty = msgs.length === 0 && !loading && !isEstudar;

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

      {/* Onboarding */}
      {!onboarded && (
        <Onboarding onFinish={() => setOnboarded(true)} />
      )}

      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>

        {/* Sidebar (desktop only) */}
        {!isMobile && (
          <Sidebar
            mode={mode}
            onModeChange={switchMode}
            onStudyTrecho={handleStudyTrecho}
            onTutorial={() => setOnboarded(false)}
            conversations={conversations}
            onLoadConvo={(c) => { setMode(c.mode); setMsgs(c.msgs); setConvoId(c.id); }}
            favorites={favorites}
            evangelhoData={evangelhoData}
          />
        )}

        {/* Main area */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, background: theme.chatBg }}>

          {/* Top bar */}
          <TopBar mode={mode} theme={theme} onOpenSettings={() => setShowSettings(true)} />

          {/* Content */}
          {isEstudar && estudarSub === 'picker' && (
            <EstudarPicker
              theme={theme}
              onStartTrilha={startTrilha}
              onExplorar={() => { setEstudarSub('explorar'); setExplorarMsgs([]); }}
              paths={paths}
              pathsLoading={pathsLoading}
            />
          )}

          {isEstudar && estudarSub === 'guided' && (
            <GuidedStudy
              trilha={activeTrilha}
              currentStep={guidedStep}
              messages={guidedMsgs}
              loading={guidedLoading}
              completed={guidedDone}
              theme={theme}
              fontSize={msgFontSize}
              onNext={handleGuidedNext}
              onBack={() => { setEstudarSub('picker'); setGuidedDone(false); }}
              onRedirectDuvida={(msg) => redirectToDuvida(msg?.obra?.title || 'Kardec')}
              onShare={setShareMsg}
              onToggleFav={toggleFavorite}
              isFavorite={isFavorite}
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
              onToggleFav={toggleFavorite}
              isFavorite={isFavorite}
              fontSize={msgFontSize}
            />
          )}

          {!isEstudar && (
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
                      Como posso ajudar seus estudos?
                    </div>
                    <div style={{ fontSize: 12.5, color: theme.subtext, maxWidth: 300, lineHeight: 1.72, marginBottom: 22 }}>
                      Faça uma pergunta ou experimente uma das sugestões abaixo.
                    </div>
                    <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap', justifyContent: 'center' }}>
                      {[
                        'O que é o perispírito?',
                        'Q.132 — Visibilidade dos Espíritos',
                        'Estou enfrentando uma perda difícil',
                        'Trecho do dia',
                      ].map(s => (
                        <button key={s} onClick={() => { setInput(s); setTimeout(handleSend, 10); }} style={{
                          background: 'rgba(107,155,184,.08)', border: '1px solid rgba(107,155,184,.26)',
                          color: '#4A7A98', fontSize: 12, padding: '6px 13px',
                          borderRadius: 16, cursor: 'pointer', fontWeight: 500,
                        }}>{s}</button>
                      ))}
                    </div>
                  </div>
                )}

                {msgs.map(msg => (
                  msg.isUser
                    ? <UserBubble key={msg.id} text={msg.text} />
                    : <AIMessage key={msg.id} msg={msg} theme={theme} fontSize={msgFontSize}
                        onShare={() => setShareMsg(msg)}
                        onToggleFav={() => toggleFavorite(msg)}
                        isFavorite={isFavorite(msg.id)}
                        showQuickActions={true}
                        quickActions={QUICK_ACTIONS}
                      />
                ))}
                {loading && <LoadingDots theme={theme} />}
              </div>

              {/* Input */}
              <InputBar
                value={input}
                onChange={setInput}
                onSend={handleSend}
                placeholder={MODE_PLACEHOLDER[mode] || ''}
                footerHint="IA treinada no Pentateuco Espírita · Respostas sempre referenciadas em Kardec · Enter para enviar"
                theme={theme}
              />
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
    </div>
  );
}

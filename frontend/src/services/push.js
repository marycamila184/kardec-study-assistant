// A conversa do navegador com o push: registrar o worker, assinar, cancelar.
//
// O worker é registrado SÓ quando a pessoa liga o lembrete. Quem nunca liga
// nunca ganha um service worker — não há motivo para instalar um em todo
// visitante quando ele só serve para isto.
import { API_BASE } from './api';

const VAPID = import.meta.env.PUBLIC_VAPID_KEY || '';

// Astro expõe PUBLIC_, não VITE_. Trocar o prefixo foi o que gravou
// localhost:8000 no bundle de produção em 2026-08-09; scripts/check_api_base.mjs
// existe por causa disso.

export function isIOS() {
  return /iPad|iPhone|iPod/.test(navigator.userAgent);
}

export function isStandalone() {
  return window.matchMedia('(display-mode: standalone)').matches
    || window.navigator.standalone === true;
}

export function pushSupported() {
  return 'serviceWorker' in navigator
    && 'PushManager' in window
    && 'Notification' in window;
}

/** No iPhone, push só existe para app já instalado na tela de início. */
export function needsInstallFirst() {
  return isIOS() && !isStandalone();
}

function urlBase64ToUint8Array(base64) {
  const pad = '='.repeat((4 - (base64.length % 4)) % 4);
  const bruto = atob((base64 + pad).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from([...bruto].map((c) => c.charCodeAt(0)));
}

async function registration() {
  // O ?api= é como o worker descobre onde fica a API: ele não lê
  // import.meta.env, e a API está noutra origem. O scope continua sendo '/'
  // porque a query não muda o caminho do script.
  return navigator.serviceWorker.register(
    `/sw.js?api=${encodeURIComponent(API_BASE)}`, { scope: '/' });
}

/** Devolve { ok, motivo } — 'permissao' | 'limite' | 'erro' | null. */
export async function subscribe(hour) {
  if (!pushSupported() || needsInstallFirst()) return { ok: false, motivo: 'erro' };

  const permissao = await Notification.requestPermission();
  if (permissao !== 'granted') return { ok: false, motivo: 'permissao' };

  try {
    const reg = await registration();
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(VAPID),
    });
    const json = sub.toJSON();

    const r = await fetch(`${API_BASE}/push/subscribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        endpoint: sub.endpoint,
        keys: json.keys,
        hour,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      }),
    });
    if (r.ok) return { ok: true, motivo: null };
    // 429 é o teto por IP do backend. Vale distinguir porque é o único caso
    // em que "tente daqui a pouco" é conselho verdadeiro.
    return { ok: false, motivo: r.status === 429 ? 'limite' : 'erro' };
  } catch {
    // Chave VAPID vazia, permissão revogada no meio, rede caída. Quem chama
    // precisa saber que falhou; o motivo exato não muda o que dá para dizer.
    return { ok: false, motivo: 'erro' };
  }
}

export async function unsubscribe() {
  if (!('serviceWorker' in navigator)) return;
  const reg = await navigator.serviceWorker.getRegistration();
  const sub = reg && (await reg.pushManager.getSubscription());
  if (!sub) return;

  // Avisa o servidor ANTES de desfazer localmente: se a ordem fosse a
  // inversa e a chamada falhasse, o registro ficaria órfão no store sem
  // ninguém do lado do navegador para removê-lo depois.
  const r = await fetch(`${API_BASE}/push/unsubscribe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ endpoint: sub.endpoint }),
  });
  if (!r.ok) throw new Error(`unsubscribe falhou: ${r.status}`);
  await sub.unsubscribe();
}

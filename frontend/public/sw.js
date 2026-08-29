// Service worker do lembrete — e SÓ do lembrete.
//
// Registra `push` e `notificationclick`. NÃO tem handler de `fetch`, não faz
// cache e não intercepta requisição nenhuma. Isso não é economia: é o que
// reconcilia este arquivo com a decisão de não ter service worker tomada em
// docs/superpowers/specs/2026-08-27-pwa-instalavel-design.md, que era contra
// um worker capaz de fixar uma versão velha no aparelho da pessoa em
// silêncio. Sem handler de `fetch`, isso é estruturalmente impossível.
//
// scripts/check_push_service_worker.mjs derruba o CI se um `fetch` aparecer
// aqui. A reconciliação só vale enquanto este arquivo continuar deste
// tamanho.

self.addEventListener('push', (event) => {
  // O parse fica dentro de um try porque acontece ANTES do waitUntil: um
  // payload malformado levantaria aqui e o navegador não mostraria nada —
  // pior que um lembrete feio é um lembrete que não aparece.
  let dados = {};
  try {
    dados = event.data ? event.data.json() : {};
  } catch {
    dados = {};
  }
  event.waitUntil(
    self.registration.showNotification(dados.title || 'Dialogando com a Doutrina', {
      body: dados.body || '',
      icon: '/icons/icon-192.png',
      badge: '/icons/icon-192.png',
      data: { url: dados.url || '/' },
    }),
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const destino = (event.notification.data && event.notification.data.url) || '/';

  event.waitUntil((async () => {
    // Carimba last_seen. É o que faz os 90 dias existirem — sem nada
    // registrando atividade, a expiração nunca dispararia. Só a data.
    try {
      const sub = await self.registration.pushManager.getSubscription();
      if (sub) {
        // A base da API vem na query do próprio worker: um service worker não
        // enxerga import.meta.env, e a API mora noutra origem (Cloud Run), de
        // modo que um fetch relativo bateria na Vercel e devolveria HTML.
        // Quem registra o worker põe o ?api= — ver services/push.js.
        const base = new URL(self.location.href).searchParams.get('api') || '';
        await fetch(`${base}/push/seen`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ endpoint: sub.endpoint }),
        });
      }
    } catch { /* carimbar é melhor-esforço; nunca impede de abrir o app */ }

    const abertas = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const cliente of abertas) {
      if ('focus' in cliente) {
        // Focar sem navegar deixa a pessoa na tela em que já estava, e o
        // lembrete prometeu o trecho do dia. Navegar pode falhar (o cliente
        // precisa ser da mesma origem), e nesse caso focar ainda é melhor
        // que nada.
        if ('navigate' in cliente) {
          try { await cliente.navigate(destino); } catch { /* segue e foca */ }
        }
        return cliente.focus();
      }
    }
    return self.clients.openWindow(destino);
  })());
});

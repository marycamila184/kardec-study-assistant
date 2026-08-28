// O lembrete diário, agora por Web Push.
//
// A versão anterior era um setInterval dentro da página e só disparava com a
// aba aberta em primeiro plano — foi desligada em 2026-08-05 por não poder
// funcionar. Ver docs/superpowers/specs/2026-08-27-lembrete-push-design.md
import { useEffect, useState } from 'react';

import { needsInstallFirst, pushSupported, subscribe, unsubscribe } from '../services/push';
import { useStorage } from './useStorage';

export function useReminder() {
  // As duas chaves sobreviveram ao desligamento de 2026-08-05 de propósito:
  // quem tinha 06:30 guardado recupera o horário em vez de voltar ao padrão.
  const [enabled, setEnabled] = useStorage('dialogando_reminder_on', false);
  const [hour, setHourStored] = useStorage('dialogando_reminder_time', '08:00');
  const [busy, setBusy] = useState(false);
  const [supported, setSupported] = useState(false);
  const [needsInstall, setNeedsInstall] = useState(false);

  useEffect(() => {
    setSupported(pushSupported());
    setNeedsInstall(needsInstallFirst());
  }, []);

  const enable = async () => {
    setBusy(true);
    const ok = await subscribe(hour);
    setEnabled(ok);
    setBusy(false);
    return ok;
  };

  const disable = async () => {
    setBusy(true);
    await unsubscribe();
    setEnabled(false);
    setBusy(false);
  };

  // Trocar a hora com o lembrete ligado exige reassinar: a hora vive no
  // registro do servidor, não no navegador.
  const setHour = async (nova) => {
    setHourStored(nova);
    if (enabled) {
      setBusy(true);
      await subscribe(nova);
      setBusy(false);
    }
  };

  return { supported, needsInstall, enabled, hour, setHour, enable, disable, busy };
}

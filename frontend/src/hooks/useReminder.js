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
  // Um horário quebrado guardado antes de o seletor virar horas cheias
  // (06:30) não casa com nenhuma opção e deixaria o campo em branco. Arredonda
  // para baixo, para a hora que a pessoa escolheu — 06:30 vira 06:00, não
  // 07:00: adiantar um lembrete é melhor que atrasá-lo.
  const horaCheia = `${(hour || '08:00').slice(0, 2)}:00`;
  const [busy, setBusy] = useState(false);
  const [supported, setSupported] = useState(false);
  const [needsInstall, setNeedsInstall] = useState(false);
  const [motivo, setMotivo] = useState(null);

  useEffect(() => {
    setSupported(pushSupported());
    setNeedsInstall(needsInstallFirst());
  }, []);

  const enable = async () => {
    setBusy(true);
    setMotivo(null);
    try {
      const r = await subscribe(hour);
      setEnabled(r.ok);
      if (!r.ok) setMotivo(r.motivo);
      return r.ok;
    } finally {
      // finally, sempre: sem ele qualquer exceção deixa o botão travado em
      // "ocupado" até a pessoa recarregar a página.
      setBusy(false);
    }
  };

  const disable = async () => {
    setBusy(true);
    setMotivo(null);
    try {
      await unsubscribe();
      setEnabled(false);
    } catch {
      setMotivo('erro');
    } finally {
      setBusy(false);
    }
  };

  // Trocar a hora com o lembrete ligado exige reassinar: a hora vive no
  // registro do servidor, não no navegador. Só grava a hora nova DEPOIS de o
  // servidor aceitar — senão o painel mostra um horário que ninguém guardou.
  const setHour = async (nova) => {
    if (!enabled) {
      setHourStored(nova);
      return true;
    }
    setBusy(true);
    setMotivo(null);
    try {
      const r = await subscribe(nova);
      if (r.ok) setHourStored(nova);
      else setMotivo(r.motivo);
      return r.ok;
    } finally {
      setBusy(false);
    }
  };

  return { supported, needsInstall, enabled, hour: horaCheia, setHour, enable, disable, busy, motivo };
}

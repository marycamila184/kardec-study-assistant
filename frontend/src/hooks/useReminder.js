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
  // A broken hour stored before the picker became whole-hours-only (06:30)
  // matches no option and would leave the field blank. Rounds down, to the
  // hour the person chose — 06:30 becomes 06:00, not 07:00: bringing a
  // reminder forward beats pushing it back.
  //
  // The validation isn't caution for its own sake: the value comes from
  // localStorage, which may have been written by an old version, another
  // tab, or by hand. A number stored there has no .slice and would crash the
  // whole Settings panel render — and "7:00" would become "7::00", which the
  // server rejects with a 422.
  const horaCheia = /^([01]\d|2[0-3]):[0-5]\d$/.test(hour)
    ? `${hour.slice(0, 2)}:00`
    : '08:00';
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
      const r = await subscribe(horaCheia);
      setEnabled(r.ok);
      if (!r.ok) setMotivo(r.motivo);
      return r.ok;
    } finally {
      // always finally: without it any exception leaves the button stuck in
      // "busy" until the person reloads the page.
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

// Day dividers in a message thread.
//
// Everything here works on epoch milliseconds, which carry no timezone of their
// own — `new Date(ms)` renders in the reader's local time, which is what a
// divider should say. (The sidebar's trecho date is the opposite case: the API
// sends a calendar date as "YYYY-MM-DD", and parsing that with `new Date` reads
// it as UTC midnight and shows the previous day in Brazil. Different input,
// different rule — see formatTrechoDate in Sidebar.jsx.)

const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());

/** Stable per-day key, local time. Two messages share it iff same calendar day. */
export function dayKey(ts) {
  if (!ts) return null;
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return null;
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

/**
 * "Hoje" / "Ontem" / "26 de julho" / "26 de julho de 2025".
 *
 * The year only appears when it is not the current one: a thread from this year
 * reads better without it, and one from an earlier year is misleading without.
 */
export function dayLabel(ts, now = Date.now()) {
  if (!ts) return null;
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return null;

  const today = startOfDay(new Date(now));
  const days = Math.round((today - startOfDay(d)) / 86400000);
  if (days === 0) return 'Hoje';
  if (days === 1) return 'Ontem';

  return d.toLocaleDateString('pt-BR', {
    day: 'numeric',
    month: 'long',
    ...(d.getFullYear() !== today.getFullYear() ? { year: 'numeric' } : {}),
  });
}

/**
 * Should a divider be drawn above `msgs[index]`?
 *
 * True for the first message that has a time, and thereafter whenever the day
 * changes. Messages with no `ts` — every thread saved before timestamps existed
 * — never draw one: an undated message must not be labelled with a day it may
 * not belong to.
 */
export function startsNewDay(msgs, index) {
  const key = dayKey(msgs[index]?.ts);
  if (!key) return false;
  for (let i = index - 1; i >= 0; i -= 1) {
    const prev = dayKey(msgs[i]?.ts);
    if (prev) return prev !== key;
  }
  return true;
}

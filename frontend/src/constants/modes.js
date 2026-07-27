// frontend/src/constants/modes.js
//
// One source of truth for the three modes' display metadata. The home launcher
// and the "Nova conversa" dropdown both render from this array, so they cannot
// drift apart — the spec requires the menu mirror the home cards one-for-one.
//
// `id` is the persisted state key. It is written into every saved conversation
// and mapped to the backend's intent vocabulary by MODE_TO_INTENT in App.jsx.
// NEVER rename an id: it would orphan conversations already in a reader's
// localStorage. Labels are display-only and safe to change.

export const MODES = [
  {
    id: 'estudar',
    label: 'Estudar',
    desc: 'Trilhas guiadas e livre exploração pelas 5 obras',
    icon: '📚',
  },
  {
    id: 'duvida',
    label: 'Dialogar',
    desc: 'Perguntas abertas fundamentadas nas obras de Kardec',
    icon: '💬',
  },
  // Refletir is switched off for production — the mode is disconnected, not
  // deleted. See docs/superpowers/specs/2026-07-26-desligar-reflexivo-design.md
  // {
  //   id: 'refletir',
  //   label: 'Refletir',
  //   desc: 'Relacione situações da vida aos ensinamentos da doutrina',
  //   icon: '🪞',
  // },
];

// TopBar's existing lookup shape, derived so the two never disagree.
export const MODE_META = Object.fromEntries(
  MODES.map(m => [m.id, { title: m.label, desc: m.desc }])
);

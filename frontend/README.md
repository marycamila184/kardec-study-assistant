# Frontend: Dialogando com a Doutrina

## Overview
A chatbot study companion for Spiritist doctrine, built around Allan Kardec's five works (the Pentateuco Espírita). The frontend provides four study modes, a guided trilha system with Socratic tutoring, a free exploration mode, dark mode, settings, share cards, clickable source citations, and persistent conversation history.

> **Note:** this file started as a pre-implementation design handoff (recreate the `reference/` HTML mockup in React). Implementation is complete — the "Component Architecture", "API Integration", and "localStorage Keys" sections below describe the app **as built**, not a spec to build toward. Design Tokens / Typography / Spacing are still accurate as visual reference.

## About the Design Files
The `reference/` folder contains the original **HTML design prototype** — kept for historical/visual reference. It is not production code and may no longer match the app pixel-for-pixel where implementation diverged from the mockup.

---

## Tech Stack
- React 18 with hooks
- Vite 5 (build tool)
- No CSS framework — inline `style={{...}}` objects with light/dark theme token objects (`src/constants/theme.js`)
- localStorage for persistence (no backend session/auth)
- `fetch` for API calls (`src/services/api.js`)

---

## Design Tokens

### Colors
```js
// Primary
'#6B9BB8'  // Sky blue — primary brand, sidebar bg, user bubbles, buttons
'#5A8AA6'  // Sky blue hover
'#C8856A'  // Terracotta — "Da Obra" badge, loading dots, accent

// Light theme
chatBg:       '#F6F4EF'
headerBg:     '#FDFBF8'
headerBorder: '#E6E0D8'
cardBg:       '#FFFFFF'
cardBorder:   '#E2DDD6'
obraBg:       '#FBF8F2'
obraBorder:   '#DDD0B8'
text:         '#3A3028'
subtext:      '#9A8E7E'
obraText:     '#4A3020'
inputBg:      '#FFFFFF'
inputBorder:  '#DDD7CE'

// Dark theme
chatBg:       '#111C26'
headerBg:     '#162030'
headerBorder: '#1F2F3D'
cardBg:       '#1C2D3C'
cardBorder:   '#253748'
obraBg:       '#1E3040'
obraBorder:   '#2C4258'
text:         '#D5CCC0'
subtext:      '#6A8898'
obraText:     '#C5B49A'
sideBg (dark): '#1B3248'
```

### Typography
```css
/* Import in index.html or CSS */
@import url('https://fonts.googleapis.com/css2?family=Crimson+Pro:ital,wght@0,300;0,400;0,600;1,300;1,400;1,600&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap');

/* Body */       font-family: 'DM Sans', system-ui, sans-serif;
/* Quotes */     font-family: 'Crimson Pro', serif; font-style: italic; font-size: 17px;
/* Brand title */font-family: 'Crimson Pro', serif; font-size: 18px; font-weight: 600;
/* Headings */   font-family: 'Crimson Pro', serif;
```

### Spacing
4 / 6 / 8 / 10 / 12 / 14 / 16 / 18 / 20 / 24 / 28 / 32 / 40px

### Border Radius
6px (small), 8px (medium), 10px (cards), 14px (pills), 50% (avatars)

### Shadows
`box-shadow: 0 2px 24px rgba(80,110,140,.18)` — main app container

---

## Screens / Views

### 1. Onboarding (3 steps)
- **Step 0 — Welcome**: Full-screen centered card. Brand icon (60px circle, sky blue), title "Dialogando com a Doutrina" (38px Crimson Pro), tagline "Estude · Reflita · Compreenda", description paragraph, blue info box about AI scope, "Começar →" button. Progress dots (3).
- **Step 1 — 4 Modes**: 2×2 grid of mode cards (white, border, 10px radius). Each card has icon (34px square, rounded, light blue bg), mode title (13px, 600), description (12px, subtext). "Entendi →" button.
- **Step 2 — Choose Obra**: Title, 6 pill buttons for obras (selected = sky blue fill), "Começar a estudar →" button.
- Persists to localStorage key `dialogando_onboarded`.

### 2. Main Layout
- **Sidebar** (300px, sky blue `#6B9BB8`): Brand header (clickable — opens the tutorial/onboarding overlay, same as the "Ver tutorial" button below), mode nav, daily trecho card, recent convos, favorites, "Ver tutorial" button (second, redundant entry point to the same `onTutorial` action).
- **Chat Area** (flex:1): Top header bar with mode icon + title + settings gear. Messages scroll area. Input bar (non-estudar modes).
- **Mobile**: Sidebar collapses, bottom nav bar (4 mode icons), hamburger opens drawer.

### 3. Tirar uma Dúvida / Refletir (chat modes)
- Empty state: centered icon, title "Em que posso ajudar?", subheading "Escolha uma sugestão ou digite sua pergunta.", a distinct "📚 Estudar uma Obra" navigation card (switches to the Estudar uma Obra picker), and 4 suggestion pills (📖 O que é o Espiritismo? · 💬 alma/perispírito/espírito · 🔄 reencarnação · 🪞 mais paz no dia a dia) that each send that question via `/chat` (or `/reflect` in Refletir mode).
- Message flow: User bubble (right, sky blue), AI response (left, with avatar).
- **AI Response structure** (`AIMessage.jsx` = `ObraBlock` + `IABlock`):
  1. "Da Obra" block (cream bg `#FBF8F2`, amber border `#DDD0B8`): badge + obra title + italic quote (17px Crimson Pro) + citation. Only rendered when `msg.hasDaObra`.
  2. Divider (1px, `#DDD0B8`).
  3. "Da IA" block (white, gray border): "Da IA" badge + share icon + fav icon + explanation text. The explanation text reveals progressively via a typewriter effect (`useTypewriter` hook, keyed off `msg.id`) rather than appearing instantly — client-side animation only, the full response already arrived from the API.
  4. **Source citation chips** (independent of quick actions, always shown when present): one `📖 book, Q.N` chip per source; clicking opens `SourceModal` with that source's excerpt.
  5. Quick action pills (currently disabled everywhere — `showQuickActions={false}` in every render site, pending redesign): 📄 Ler original · 💡 Explicar simples · 🪞 Reflexão · 📚 Relacionados. "Relacionados" opens `RelatedItemsModal` (a list of related items, click-through to full study) rather than dumping text into the chat.
- Loading state: 3 dots animation (`dot-pulse`), color `#C8856A`.

### 4. Estudar uma Obra
- **Picker screen** (`EstudarPicker.jsx`): "Quem foi Kardec?" card + O Pentateuco Espírita list (5 obra cards with abbr, title, summary, year) + Trilhas guiadas (shows a "✓ Concluída" badge for completed trilhas, from `completedTrilhas` localStorage state) + Explorar Obras card.
- **Guided Trilha** (`GuidedStudy.jsx`): progress bar (4px fill; turns green `#4CAF50` at 100%, otherwise sky blue), step label ("X de 8"), back button. Each card's title line includes "· Passo N de M" so scrolling back through a multi-step conversation shows which step it belongs to. Neither the favorite star nor the share icon appear on any card in this mode (nor in Explorar Obras) — `onShare`/`onToggleFav`/`isFavorite` are simply not forwarded to `AIMessage` here. Last-step message shows "Concluir trilha ✨" / other steps show "Entendi, próximo →", plus a "Tenho uma dúvida" ghost button. Clicking "Concluir trilha" persists to `completedTrilhas`, then opens `TrilhaCompleteModal` — a small "Trilha concluída! 🌟" confirmation with a "Compartilhar" button (opens the existing `ShareModal` with the trilha's last passage) and a "Continuar" button; either one navigates back to the picker once dismissed. There is no separate full-screen "Trilha concluída!" takeover anymore (removed in an earlier pass; it wasn't working reliably) — this small modal replaced it and is also where sharing now lives for this mode.
- **Explorar Obras screen** (`ExplorarObras.jsx`): 5 obra cards in grid header (abbr + shortLabel, active = blue border). Expandable topic sections (accordion). Each section shows context description + topic pill buttons. Same as Guided Trilha, no favorite/share icons appear here.

### 5. Settings Panel (slide-in from right, 300px)
- Sections: Aparência (dark toggle + font size buttons), Sobre esta IA (scope explanation + obras list + warning), Idioma (PT-BR active, EN disabled), Lembrete (toggle + time picker + notification permission button).
- Dark toggle: 40×22px pill, knob slides left/right.
- Font size: 3 buttons (Pequena/Média/Grande), selected = sky blue fill.
- Lembrete time picker shows a brief "Salvo ✓" acknowledgment (local component state, fades after ~1.5s) whenever the reminder time is changed — purely a UI confirmation, not persisted itself. Clicking the daily reminder's browser notification focuses the app and navigates to the daily trecho view (same destination as the sidebar's "☀️ Trecho do dia" card).

### 6. Share Modal (centered overlay)
- Preview card (blue gradient bg `#3A6E8A`→`#2A5070`): app name label + italic quote (20px Crimson Pro, white) + divider + citation.
- Actions: "Copiar texto" (copy to clipboard) + "Baixar imagem" (canvas PNG 960×560).
- Triggered either by the per-message share icon (in `/chat`/`/reflect`, currently gated by `showQuickActions`) or from `TrilhaCompleteModal`'s "Compartilhar" button (Guided Trilha completion) — same modal, different entry points.

---

## Component Architecture
Actual current tree (see `src/` for implementations):

```
src/
  App.jsx                     # Root — all mode/chat/trilha state, wires everything together
  services/
    api.js                    # fetch wrappers + response-mapping (mapChat/mapStudy/mapReflect) for every endpoint
  components/
    layout/
      Sidebar.jsx             # Sidebar with nav, daily trecho, recent convos, favorites, "Ver tutorial"
      MobileBottomNav.jsx     # Bottom tab bar (mobile only) — no separate mobile drawer component
      TopBar.jsx              # Chat header with mode icon + title + settings gear
    chat/
      UserBubble.jsx          # Right-aligned user message
      AIMessage.jsx           # Full AI response wrapper (ObraBlock + IABlock)
      ObraBlock.jsx           # "Da Obra" cream section with quote
      IABlock.jsx             # "Da IA" section — explanation text, citation chips, quick actions, SourceModal
      LoadingDots.jsx         # 3-dot pulse animation
      InputBar.jsx            # Textarea + send button + footer hint
    modes/
      EstudarPicker.jsx       # Who was Kardec + Pentateuco + Trilhas (with completion badges) + Explorar
      GuidedStudy.jsx         # Progress bar + guided chat + next/conclude/duvida buttons
      ExplorarObras.jsx       # Obra cards header + accordion topics
      IntroObras.jsx          # "Sobre as Obras" — Kardec bio + obras overview
    modals/
      Onboarding.jsx          # 3-step onboarding overlay
      SettingsPanel.jsx       # Slide-in settings drawer
      ShareModal.jsx          # Share quote modal (copy text / download PNG card)
      SourceModal.jsx         # Citation excerpt modal (opened from IABlock's source chips)
      RelatedItemsModal.jsx   # Related-items list, click-through to full /study
      TrilhaCompleteModal.jsx # Guided trilha completion confirmation + share action
  hooks/
    useTheme.js               # darkMode state + localStorage persistence
    useStorage.js             # Generic localStorage-backed useState hook
    useConversations.js       # Save/load conversation history
    useFavorites.js           # Bookmark AI responses
    useReminder.js            # Browser notification interval; onNotificationClick kept in a ref internally so a fresh callback identity on every render doesn't tear down/rebuild the interval
    useTypewriter.js          # Progressive text-reveal hook (client-side only, no backend streaming)
  constants/
    theme.js                  # Light/dark token objects
    obras.js                  # 5 obras with summaries, abbr, topics
  styles/
    globals.css               # @font-face, body reset, scrollbar, animations
```

There is no `QuickActions.jsx` or `EmptyState.jsx` — those pieces live inline in `IABlock.jsx` and `App.jsx` respectively. There is no `constants/trilhas.js` — trilha data comes from the backend's `GET /paths` / `GET /paths/{id}` endpoints, not a local constant.

---

## API Integration
All backend calls go through `src/services/api.js`, which wraps `fetch` and maps each endpoint's raw JSON into the shape the UI components expect. Base URL: `import.meta.env.VITE_API_URL || 'http://localhost:8000'`.

```js
// src/services/api.js (actual functions)
chatMessage(question, history)              // POST /chat  → { hasDaObra: false, obra: null, ia, sources }
studyItem(book, item_number, chapter=null)   // POST /study → { hasDaObra: true, obra: {...}, ia, relatedItems, sources }
reflectSituation(situation)                  // POST /reflect → { hasDaObra: false, obra: null, ia, relatedItems, sources }
getEvangelho()                               // GET /evangelho → { date, content, source }
getPaths()                                   // GET /paths → [{ id, title, description, level, step_count }]
getPath(pathId)                              // GET /paths/{id} → { id, title, description, level, steps }
```

`sources` items are `{ book, item_number, excerpt }` — rendered as clickable citation chips. `relatedItems` items are `{ book, chapter, item_number, preview, conexao }` — rendered in `RelatedItemsModal`, click-through calls `studyItem(item.book, item.item_number, item.chapter)`.

---

## localStorage Keys
| Key | Type | Purpose |
|-----|------|---------|
| `dialogando_onboarded` | boolean | Skip onboarding |
| `dialogando_dark` | boolean | Dark mode |
| `dialogando_fontsize` | string `'small'/'medium'/'large'` | Font size |
| `dialogando_convos` | JSON array | Conversation history |
| `dialogando_favs` | JSON array | Favorited AI responses |
| `dialogando_reminder_on` | boolean | Reminder enabled |
| `dialogando_reminder_time` | string `'HH:MM'` | Reminder time |
| `dialogando_completed_trilhas` | JSON array of trilha ids | Drives the "✓ Concluída" badge in `EstudarPicker` |

All keys go through the generic `useStorage(key, defaultValue)` hook (`src/hooks/useStorage.js`), which JSON-serializes and syncs to `localStorage` on every update.

---

## Files
- `reference/Dialogando com a Doutrina.dc.html` — original interactive prototype (historical reference, open in browser)
- `src/` — the actual, current implementation

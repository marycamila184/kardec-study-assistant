# Handoff: Dialogando com a Doutrina

## Overview
A chatbot study companion for Spiritist doctrine, built around Allan Kardec's five works (the Pentateuco Espírita). The frontend provides four study modes, a guided trilha system with Socratic tutoring, a free exploration mode, dark mode, settings, share cards, and persistent conversation history.

## About the Design Files
The `reference/` folder contains the **HTML design prototype** — a high-fidelity interactive mockup showing the intended look, behavior, and interactions. It is NOT production code. Your task is to **recreate these designs in React** using the component structure provided in `src/`.

## Fidelity
**High-fidelity.** Pixel-accurate colors, typography, spacing, and interactions. Recreate the UI exactly using the provided React components and design tokens.

---

## Tech Stack (recommended)
- React 18+ with hooks
- React Router v6 (for future routing)
- CSS Modules or Tailwind CSS
- localStorage for persistence
- Fetch/Axios for RAG API calls

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
- **Sidebar** (300px, sky blue `#6B9BB8`): Brand header, mode nav, daily trecho card, recent convos, favorites, "Ver tutorial" button.
- **Chat Area** (flex:1): Top header bar with mode icon + title + settings gear. Messages scroll area. Input bar (non-estudar modes).
- **Mobile**: Sidebar collapses, bottom nav bar (4 mode icons), hamburger opens drawer.

### 3. Tirar uma Dúvida / Refletir (chat modes)
- Empty state: centered icon, title "Como posso ajudar seus estudos?", 4 suggestion pill buttons.
- Message flow: User bubble (right, sky blue), AI response (left, with avatar).
- **AI Response structure**:
  1. "Da Obra" block (cream bg `#FBF8F2`, amber border `#DDD0B8`): badge + obra title + italic quote (17px Crimson Pro) + citation.
  2. Divider (1px, `#DDD0B8`).
  3. "Da IA" block (white, gray border): "Da IA" badge + share icon + fav icon + explanation text + historical context line.
  4. Quick action pills: 📄 Ler original · 💡 Explicar simples · 🪞 Reflexão · 🏛 Contexto histórico · 📚 Relacionados · 🔖 Salvar.
- Loading state: 3 dots animation (`dot-pulse`), color `#C8856A`.

### 4. Estudar uma Obra
- **Picker screen**: "Quem foi Kardec?" card + O Pentateuco Espírita list (5 obra cards with abbr, title, summary, year) + Trilhas guiadas + Explorar Obras card.
- **Guided Trilha**: Progress bar (4px, sky blue fill, animated width), step label ("X de 8"), back button. Messages show "Da Obra" block + "Tutor" badge + question + "Entendi, próximo →" / "Concluir trilha ✨" buttons centered + "Tenho uma dúvida" ghost button.
- **Completion screen**: ✨ emoji in circle, "Trilha concluída!", back to picker buttons.
- **Explorar Obras screen**: 5 obra cards in grid header (abbr + shortLabel, active = blue border). Expandable topic sections (accordion). Each section shows context description + topic pill buttons.

### 5. Settings Panel (slide-in from right, 300px)
- Sections: Aparência (dark toggle + font size buttons), Sobre esta IA (scope explanation + obras list + warning), Idioma (PT-BR active, EN disabled), Lembrete (toggle + time picker + notification permission button).
- Dark toggle: 40×22px pill, knob slides left/right.
- Font size: 3 buttons (Pequena/Média/Grande), selected = sky blue fill.

### 6. Share Modal (centered overlay)
- Preview card (blue gradient bg `#3A6E8A`→`#2A5070`): app name label + italic quote (20px Crimson Pro, white) + divider + citation.
- Actions: "Copiar texto" (copy to clipboard) + "Baixar imagem" (canvas PNG 960×560).

---

## Component Architecture
See `src/` folder for full implementations.

```
src/
  App.jsx                     # Root — wires state, theme, routing between modes
  components/
    layout/
      Sidebar.jsx             # 300px sidebar with nav, trecho, recents, favs
      MobileDrawer.jsx        # Full-screen drawer for mobile
      MobileBottomNav.jsx     # Bottom tab bar (mobile only)
      TopBar.jsx              # Chat header with mode icon + settings gear
    chat/
      ChatMessages.jsx        # Messages scroll container
      UserBubble.jsx          # Right-aligned user message
      AIMessage.jsx           # Full AI response (ObraBlock + IABlock)
      ObraBlock.jsx           # "Da Obra" cream section with quote
      IABlock.jsx             # "Da IA" section with explanation
      QuickActions.jsx        # Pill buttons row
      LoadingDots.jsx         # 3-dot pulse animation
      InputBar.jsx            # Textarea + send button + footer hint
      EmptyState.jsx          # Welcome state with suggestions
    modes/
      EstudarPicker.jsx       # Who was Kardec + Pentateuco + Trilhas + Explorar
      GuidedStudy.jsx         # Progress bar + guided chat + next/duvida buttons
      ExplorarObras.jsx       # Obra cards header + accordion topics
    modals/
      Onboarding.jsx          # 3-step onboarding overlay
      SettingsPanel.jsx       # Slide-in settings drawer
      ShareModal.jsx          # Share quote modal
  hooks/
    useTheme.js               # darkMode state + localStorage persistence
    useStorage.js             # Generic localStorage hook
    useConversations.js       # Save/load conversation history
    useFavorites.js           # Bookmark AI responses
    useReminder.js            # Browser notification interval
  constants/
    theme.js                  # Light/dark token objects
    obras.js                  # 5 obras with summaries, abbr, topics
    trilhas.js                # Trilha data with steps, quotes, tutor questions
  styles/
    globals.css               # @font-face, body reset, scrollbar, animations
```

---

## API Integration Points
Replace simulated responses with real RAG calls:

```js
// In ChatMessages / GuidedStudy / ExplorarObras:
const response = await fetch('/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    mode,          // 'duvida' | 'refletir' | 'estudar' | 'diario'
    query,         // user text
    obra,          // 'le' | 'lm' | 'ese' | 'ci' | 'gen' | null
    conversationId // for context
  })
});
// Expected response shape:
{
  obra: { title, quote, citation, context } | null,
  ia: string,   // explanation text
  hasDaObra: boolean
}
```

---

## localStorage Keys
| Key | Type | Purpose |
|-----|------|---------|
| `dialogando_onboarded` | string `'true'` | Skip onboarding |
| `dialogando_dark` | string `'true'/'false'` | Dark mode |
| `dialogando_fontsize` | string `'small'/'medium'/'large'` | Font size |
| `dialogando_obra` | string obra id | Selected obra |
| `dialogando_convos` | JSON array | Conversation history (max 20) |
| `dialogando_favs` | JSON array | Favorited AI responses |
| `dialogando_reminder_on` | string | Reminder enabled |
| `dialogando_reminder_time` | string `'HH:MM'` | Reminder time |

---

## Files
- `reference/Dialogando com a Doutrina.dc.html` — Full interactive prototype (open in browser)
- `src/` — React component scaffolds ready to implement

# An installable app, without a service worker

**Date:** 2026-08-27
**Status:** implemented

## What was asked for

A reader who studies here every day has no way to keep the app on their phone.
They open a browser, find a tab or type an address, and get a page. The request
was to "turn it into an app" — with the immediate caveat, from the author, that
native app development is out of reach and not wanted.

Three outcomes were named: an icon on the home screen, opening faster, and the
daily reminder back.

## Scope: the reminder is not in this spec

The reminder is [2026-08-05-desligar-lembrete-design](2026-08-05-desligar-lembrete-design.md),
and that decision was not made on effort. It was made on storage: delivering a
notification with the app closed requires Web Push, and a stored push
subscription is a durable per-device identifier held server-side, carrying the
hour a named device studies. This backend has been deliberate about never
holding one — it never generates a `session_id` and never derives one, and the
absence of the `X-Session-Id` header IS the refusal.

That spec left an explicit gate: whether push is worth building "depends on how
much of the audience is on iPhone — measurable in Vercel Analytics, not
guessable." That measurement has not been taken. Reopening the decision inside a
spec about a manifest would decide it by momentum instead of by the gate it was
given.

So the reminder is deferred to its own spec, and **the ordering costs nothing**:
on iOS, Web Push exists only for a web app already installed to the Home Screen.
The manifest is a prerequisite of the reminder either way. Doing this first is
the reminder's first step, not a delay of it.

## The two findings that shrank this work

The design that was approved is smaller than the one that was proposed, because
two assumptions were checked instead of carried.

### A service worker is not required to install

The expensive half of "make it a PWA" is usually the service worker. It is not
needed here.

Chrome removed the requirement for a service worker implementing `fetch()` for
installation from the menu — since version 108 on mobile and 112 on desktop
([Chrome for Developers](https://developer.chrome.com/blog/update-install-criteria)).
MDN is explicit that a service worker is "not a requirement for a PWA to be
installable"; it is a requirement for an offline experience, which nobody asked
for ([MDN](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable)).
On iOS, Add to Home Screen never depended on one; what matters there is
`display: standalone`.

**The honest caveat, recorded so nobody is surprised:** Chrome's *automatic*
install prompt — the banner that appears unprompted — still wants a `fetch()`
handler. Without a service worker, installation is available through the browser
menu ("Install app" / "Add to Home Screen") but the spontaneous invitation may
not appear. That is a real reduction in discoverability, accepted here in
exchange for not shipping a component whose characteristic failure is pinning a
stale version onto a reader's device silently.

### "Opens faster" is already done

Measured against production on 2026-08-27:

| Resource | `cache-control` |
|---|---|
| `/_astro/App.<hash>.js` | `public, max-age=31536000, immutable` |
| `/_astro/client.<hash>.js` | `public, max-age=31536000, immutable` |
| `/` (the HTML) | `public, max-age=0, must-revalidate` |

The heavy files are content-hashed and held by the browser for a year, so a
second visit fetches none of them. The HTML, which is small, is revalidated
every time — which is exactly what keeps a deploy from going unnoticed.

A service worker has nothing to accelerate against that. It has something to
break: serving a cached shell that outlives the deploy it came from. This
project already documents that a failure nothing surfaces in the running app is
the kind it builds guards for. Adding a silent-staleness mechanism to fix a
slowness that measurement says is not there is the inverse of that instinct.

**Decision: no service worker.** Recorded as a decision, not an omission. If
offline reading is ever wanted — reading a trilha or the daily passage with no
signal, which is a real thing this corpus could support since the content is
already committed JSON — that is a separate spec with its own reason to exist.

## The design

### Manifest

`frontend/public/manifest.webmanifest`. `public/` is copied into `dist/`
verbatim by Astro, so no build step is added.

| Field | Value | Why |
|---|---|---|
| `name` | `Dialogando com a Doutrina` | The product name. Shown in the install invitation and the app list |
| `short_name` | `Dialogando` | What fits under the icon |
| `start_url` | `/` | |
| `scope` | `/` | Includes `/sobre/` and `/trilhas/*`, so tapping a trilha from inside the app stays in the app |
| `display` | `standalone` | Own window, no address bar. Also what iOS requires to treat it as a Home Screen web app |
| `background_color` | `#F6F4EF` | The cream of the splash screen while it loads |
| `theme_color` | `#6B9BB8` | `BRAND_BLUE`. Already the `<meta name="theme-color">` in `Base.astro` |
| `lang` | `pt-BR` | |
| `icons` | 192, 512, 512 maskable | Chromium requires both 192 and 512 to consider the manifest installable |

**`short_name` is `Dialogando`, and the reason is not length.** `Doutrina` also
fits, and says the subject outright. It was rejected because a label reading
*Doutrina* under an icon presents the app as being the doctrine rather than an
assistant for studying it — the exact distinction `/sobre/` spends a page
making, saying that answers can be wrong and that this does not replace reading
the works. A home-screen label is read by far more people than that page, and it
must not contradict it. Leaving `short_name` unset was also rejected: measured
against the real truncation, the full name loses the word "Doutrina" on both
iOS and Android, which is the word it was trying to keep.

### Icon

An open book, cream stroke on the brand blue, following the visual language
`preview.png` already established (cream `#F6F4EF`, brown `#3A3028`, blue
`#6B9BB8`).

Three candidates were rendered at real size and rejected for recorded reasons:
a serif "D" on blue (legible, but says nothing about the subject); the social
card turned into an icon, cream field with a blue edge bar (the most faithful to
what exists, and the worst survivor — the bar is eaten by Android's circular
mask and the cream field nearly vanishes against a light wallpaper); serif
quotation marks (distinctive, and the closest to what the product promises, but
too abstract to read as "study"). The open book's accepted cost is that it is
generic — it is the icon of half the reading apps in existence.

Files, all in `frontend/public/`:

| File | Size | Note |
|---|---|---|
| `icons/icon-192.png` | 192 | |
| `icons/icon-512.png` | 512 | |
| `icons/icon-maskable-512.png` | 512 | `purpose: "maskable"`, artwork inset to the safe zone so the circular crop takes only padding |
| `apple-touch-icon.png` | 180 | iOS reads the `<link>`, not the manifest. Must be opaque — iOS composites transparency onto black |
| `favicon.svg` | — | **There is no favicon today.** No file, and no `<link rel="icon">` in `Base.astro`; every tab shows the browser's blank-page glyph. The same artwork fixes it for free |

**Rasterization uses Playwright.** Neither `rsvg-convert`, `inkscape` nor
ImageMagick is present. Playwright is already a `devDependency` of the frontend
for the smoke test, so `frontend/scripts/make-icons.mjs` renders the SVG in
headless Chromium and screenshots it at each exact size. No new dependency, and
it is exposed as `npm run icons`.

It lives under `frontend/`, not beside the guards in `scripts/`, because Node
resolves dependencies from the file's own directory upward: a script in the repo
root cannot import `@playwright/test` out of `frontend/node_modules`. The root
guards are dependency-free on purpose; this one is not, so it does not belong
next to them.

`frontend/public/favicon.svg` is the single source of the geometry — served as
the favicon *and* the input this script rasterizes, so no second copy of the
artwork exists to drift. The PNGs are committed, like every other generated
asset here, and the script runs by hand when the artwork changes.

### The `<link>` tags

Three lines in `frontend/src/layouts/Base.astro` — manifest, apple-touch-icon,
icon. It is the shared layout, so `/`, `/sobre/` and `/trilhas/*` all get them.

This does **not** violate the standing rule that `/sobre/` carries no
JavaScript. `<link>` is not a script; the page still renders its content before
any bundle loads, and a crawler still sees text.

## The guard

A broken manifest does not appear on screen. The page renders perfectly and
behaves normally; only "Install app" quietly stops being offered, or the
installed icon falls back to a grey square. It is the same shape of failure as a
relative `og:image` or a missing canonical, which is why
`check_discovery_assets.mjs` exists.

`scripts/check_pwa_manifest.mjs` reads `frontend/dist/` — after the build, like
the other guards, which is why CI runs `npm run build` before the guards step —
and fails when:

1. the manifest is missing from `dist/`, or does not parse as JSON;
2. any `icons[].src`, the apple-touch-icon or the favicon points at a file that
   is not in `dist/`;
3. a PNG's real dimensions do not match the size it declares. Read from the
   PNG's IHDR chunk directly, so the guard needs no dependency;
4. `theme_color` in the manifest, `<meta name="theme-color">` in the built HTML
   and `BRAND_BLUE` in `frontend/src/constants/theme.js` disagree. **Three
   copies of one hex** — the same "several places that must agree" shape this
   repo already documents for the `/sobre/` trailing slash;
5. `short_name` is absent, or longer than 12 characters — the point of the field
   is to survive truncation, and a `short_name` that truncates is not one;
6. any built HTML page is missing `<link rel="manifest">`.

Wired into `.github/workflows/ci.yml` alongside the existing five guard
invocations.

**And one assertion in the browser.** `frontend/tests/smoke.spec.mjs` is the
only verification here that runs the JavaScript in a real browser. It gains a
check that the manifest responds 200 and parses, and that every icon it names
responds 200. The guard above reads files as text; this is what knows they are
actually served. That gap is the one this project already paid for twice on
2026-08-09.

## What this does not touch

No backend change. No `PRIVACY_NOTICE` edit and no change to `/sobre/`, because
nothing here collects, stores or transmits anything — the manifest is a static
description of how to draw a window. Conversation, favourites and trilha
progress keep living in `localStorage` exactly as they do now, which is why an
installed app resumes where the reader left off without a line of new code.

Explicitly out: the reminder and Web Push, offline reading, a service worker, an
app-owned cache, `screenshots` and `shortcuts` in the manifest.

## Testing

| What | How |
|---|---|
| Manifest and icons are complete and consistent | `scripts/check_pwa_manifest.mjs`, in CI, against `dist/` |
| They are actually served | Assertion in `frontend/tests/smoke.spec.mjs`, real browser |
| The PNGs match their declared sizes | IHDR read inside the guard |
| It installs | Manual, once, on a real Android and a real iPhone. No automation claims this — every layer above stops at the file, and the one thing that matters is a home screen |

**A pre-existing breakage found while verifying this, and not caused by it:**
`npm run smoke` aborted before running any test, here and on a pristine
`development`. Astro 7's `preview` calls `isRunByAgent()`; recognising the
environment, it starts the server detached and exits 0, and Playwright reads
that as "Process from config.webServer exited early".

**It was never failing in CI.** GitHub Actions is not an agent environment, the
detection returns false there, and preview runs in the foreground as it always
has. The breakage belongs to whoever develops with an AI assistant — which is
precisely who most needs to run the one suite here that executes the JavaScript
in a browser. Fixed separately by giving the Playwright `webServer` the
`ASTRO_PREVIEW_BACKGROUND` variable Astro itself uses to mean "you are the
server, do not detach".

The assertion added here was verified before that fix existed, by starting both
servers by hand and letting `reuseExistingServer` pick them up, and again after
it through `npm run smoke`. All five tests pass, and the new one was checked in
both directions: breaking `display` and removing an icon each make it fail with
a useful message.

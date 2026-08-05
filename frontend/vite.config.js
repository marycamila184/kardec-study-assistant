import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

/**
 * Serve the directory-index pages of `public/` in dev, the way a static host
 * does in production.
 *
 * Vite's SPA fallback answers any request that accepts HTML, and it gets there
 * before the static layer resolves `public/sobre/index.html`. So `vite dev`
 * serves the app at `/sobre/` — 200, but with the SPA's title and an empty
 * `<div id="root">` — and always would. Measured 2026-08-05, after the page was
 * reported broken locally while the built artifact was correct the whole time.
 *
 * `apply: 'serve'` — this touches the dev server and nothing else. Production
 * works because the build copies `public/` into `dist/` untouched, which is the
 * arrangement `scripts/check_discovery_assets.mjs` guards.
 *
 * Both `/sobre/` and `/sobre` serve the page, because that is what production
 * does — measured against the live site 2026-08-05, both returning 200 with the
 * page and no redirect. The trailing slash is the canonical form (it is the
 * file's real path, and one form has to be canonical), not a functional
 * requirement; see the note in CLAUDE.md, which claimed the opposite until that
 * measurement. A dev server should not be stricter than production any more
 * than it should be more forgiving.
 */
function publicDirectoryIndex() {
  return {
    name: 'public-directory-index',
    apply: 'serve',
    configureServer(server) {
      const root = server.config.publicDir;
      server.middlewares.use((req, res, next) => {
        if (req.method !== 'GET' && req.method !== 'HEAD') return next();
        const path = decodeURIComponent(req.url.split('?')[0]);
        if (path === '/') return next();

        // join() normalises "..", so the startsWith check below is what keeps a
        // crafted path from reading outside public/.
        const index = join(root, path, 'index.html');
        if (!index.startsWith(root) || !existsSync(index)) return next();

        res.setHeader('Content-Type', 'text/html; charset=utf-8');
        res.end(readFileSync(index));
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), publicDirectoryIndex()],
});

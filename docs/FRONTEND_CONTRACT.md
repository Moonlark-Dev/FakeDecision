# Frontend contract & design brief

## Hard constraints

- Public pages must **never** link to, mention, or hint at the admin backend. The admin route exists at `/admin`, but no public visual entry point is allowed.
- Every page is `noindex`; `robots.txt` disallows everything. Do not add analytics or remote fonts.
- Public UI: light, minimal, technical, credible provider. It must look like a real decision-model company, not an admin tool and not a generic AI chat clone.
- Admin UI: dense, efficient, quiet; default **light** theme, optional dark. 1px borders, small type, clear hierarchy, no giant marketing hero.
- There is no billing/pricing anywhere. Never render prices, credits, invoices or "free trial" purchase CTAs.
- No chat interface on the user site. These are typed decisions: state + questions → probabilities.
- Use the shared components/tokens in `src/components` and `src/styles/base.css`. Do not edit shared files from a page task without asking Lead.
- All API calls use `src/lib/api.ts`; sessions use `src/lib/session.ts`; toasts use `src/lib/toast.ts`.
- TypeScript strict, `pnpm exec vue-tsc --noEmit` clean, `pnpm exec vite build` clean.

## Brand

- Product: **Noema** (name comes from `/api/site`, default Noema).
- Brand logo: `logo_url` from `/api/site` (`""` = built-in inline SVG mark). The URL is versioned, so use it directly and update the favicon from it. Custom logos are uploaded in `/admin/settings` (PNG/JPEG/WebP/SVG, ≤512 KB) and stored in the data directory; the built-in mark remains the fallback.
- Line: "Typed decisions for software."
- Models: `jev-latest` (Jev 1.4) and `gemini-decision-1` (Gemini Decision 1).
- Voice: precise, calm, short sentences. No emoji. No "revolutionary".
- Public palette: warm off-white paper + near-black ink + electric blue + small lime highlight. Use generous whitespace, hairline rules, mono labels, subtle grid/decision motifs. Avoid purple gradients, glassmorphism, 3D blobs.
- Admin palette: same family, compressed. Use `--surface`, `--line`, `--muted`, badge colors from base CSS.

## Shared API / state

- `useSession().ensure()` is already called by router guards. Access `session.state.user`, `.admin`, `.site`, `.loaded`.
- `ApiError` has `status`, `detail` message, `code`.
- Date/duration helpers in `src/lib/format.ts`.
- Global `.btn`, `.input`, `.textarea`, `.select`, `.card`, `.panel`, `.badge`, `.table`, `.code-block`, `.empty` styles exist.

## Public routes (owned by public-ui)

- `/` HomePage: hero, decision primitive cards (noul/choice/score), API call sample, latency/quality strip, model cards, CTA. Credible and restrained.
- `/models` ModelsPage: model comparison cards from `/api/models`, protocol badges, context windows, code tabs.
- `/docs` DocsPage: quickstart, auth, both endpoints, request/response JSON, errors, timeout header, SDK-style examples. Sticky section nav is a plus. Must not reveal human operators.
- `/login`, `/register`: focused auth cards, proper errors, redirect to `next` or `/console`.
- `/console` ConsoleLayout: provider-console shell with sidebar/header; public brand; sign out; no admin link.
- Console pages:
  - Overview: greeting, usage snapshot (`/api/account/usage`), quick links, recent requests.
  - Playground: **OpenRouter-like tryout**. Protocol switch (System One / Gemini), model select, shared input editor, visual question builder (add noul/choice/score; edit instructions/criteria), "Run decision", elapsed time, response viewer, request preview, copy cURL examples. Must call `/api/console/playground` (session auth), not raw provider endpoints.
  - API keys: list, create with one-time secret modal, revoke.
  - Usage: totals, per-model mini bars, recent table.
  - Account: profile, password change (logs out after), legal/support footnotes.
- `/404` styled not-found.

## Admin routes (owned by admin-ui)

- `/admin/login`: separate internal login. No link from public. Light, compact, clear legal/private-use notice.
- `/admin` AdminLayout: fixed sidebar, topbar with role, connection state, sound toggle (top-right), theme toggle, sign out. Operator role hides Users/Operators/Models/Settings/Audit. Mobile drawer.
- `/admin` Overview: stat tiles (active, today total, answered, avg response), live recent queue, online operators, model distribution bars.
- `/admin/queue/:id?`: the core page. Split pane: request list left, detail right. On mobile, list/detail stack.
  - Connect `/api/admin/ws`; reconnect with backoff; snapshot from `hello`; merge events.
  - Sound: WebAudio chime (no asset) on `notify: true` for created/assigned; persisted mute toggle key `fd-admin-sound`. Browser audio unlock on first click; show a small muted/unlock hint if needed.
  - Incoming request card: model, id, protocol, age, status, assigned operator, question count, countdown.
  - Detail: human-readable input renderer for string/structured JSON/multimodal content blocks. Question cards.
  - Countdowns: time to `deadline_at` and "auto fill in" from `auto_fill_at`; red under 20%; show auto-fill disabled if null. Use a local tick corrected by `server_time` from hello/events.
  - Answer editor:
    - noul: probability slider + number + preset chips (decisive/lean/toss-up/lean-no/decisive-no), confidence display.
    - choice: radio winner + per-option probability inputs, confidence, randomize button.
    - score: level probability inputs/sliders, computed expected score, confidence, randomize.
    - per-question "Randomize" calls `POST .../randomize` with `{question_ids:[id]}`.
    - "Randomize all" calls with all IDs.
    - Draft autosave (debounced 600–900 ms) to `PUT .../draft`; submit `POST .../answer`, require every question answered, disable while submitting.
    - Completed/auto-filled requests must lock the editor and show outcome; toast.
  - Admin-only controls: reassign to an operator, cancel request.
- `/admin/history`: filters status/model/search, table, detail drawer or navigate to queue? Completed detail can be inline drawer; keep simple.
- `/admin/users`: search, list, disable/enable, reset password, inspect usage keys/recent.
- `/admin/operators`: create operator, assign model names (multi-select), enable/disable, online/active counts.
- `/admin/models`: CRUD model catalog, protocol, context, enabled, sort order, assigned operator count.
- `/admin/settings`: settings form (site name/tagline/description/announcement, logo upload/reset, registration toggle, timeouts, auto-fill toggle/lead, admin receives all, sound default, max pending, rate limit, support email). Show that server address/secret are CLI/env only.
- `/admin/audit`: simple table of actions.

## Quality bar

- Check all states: loading, empty, error, disabled, submitting.
- Accessibility: labels, keyboard focus, aria-live for toasts/status; do not rely on color alone.
- Responsive down to 380px.
- No external image/font network requests. Inline SVG or CSS ornaments only.
- Build clean. Report exact files and verification commands when done.

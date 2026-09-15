# AGENTS.md

BooruHub: aggregator for adult imageboards (Danbooru, e621, Rule34). Monorepo: `backend/` (FastAPI + async SQLAlchemy 2 + Alembic + Postgres), `frontend/` (Vue 3 + Vite + Pinia + Vitest), `nginx/` (reverse proxy serving the built SPA). No CI configured; verification is entirely local.

## Commands

Backend (run from `backend/`, use `.venv-linux/` if present):
- `pytest` — full suite; **coverage gate `--cov-fail-under=70`** is in `pytest.ini`, so a run fails below 70%.
- Unit tests need **no Postgres**: `tests/conftest.py` autouse-mocks the engine; `tests/test_integration_db.py` uses in-memory SQLite (`aiosqlite` in `requirements-dev.txt`).
- Single test: `pytest tests/test_auth.py -k name`. Note `testpaths = tests app` — tests also live colocated in `app/core/` and `app/services/`.
- Running the server locally (`uvicorn app.main:app --reload`) requires a `.env` with a real `DATABASE_URL` — startup validation fails without it. Settings load `backend/.env` then root `../.env`.

Frontend (run from `frontend/`):
- `npm run test` — vitest in **watch mode**; use `npx vitest run` (or `npm test -- run`) for a single pass.
- `npm run typecheck` — `vue-tsc --noEmit`. `npm run build` also type-checks (`vue-tsc -b`).
- Single test: `npx vitest run src/utils/cropCache.test.ts`.

There is **no lint config** (Python or JS) — don't look for one; typecheck + tests are the quality gate.

## Gotchas

- `frontend/vite.config.js` is a **gitignored build artifact** emitted by `vue-tsc -b`. Vite loads `.js` before `.ts`, so after editing `vite.config.ts`, delete a stale `frontend/vite.config.js` or `npm run dev` silently uses the old config.
- **Single-worker constraint**: the app relies on in-memory singletons (rate limiting, tag cache). Never increase `--workers`; Dockerfile CMD is pinned to `--workers 1`.
- **CSRF**: all `POST/PUT/DELETE` under `/api` require cookie `csrftoken` == header `X-CSRF-Token`, except `/api/auth/login`, `/api/auth/register`, `/api/health` (middleware in `app/main.py`). Tests bypass it because the middleware skips hostname `test` (ASGITransport base URL).
- Deployment: only `nginx` is published (port `${APP_PORT:-8080}`); it serves `frontend/dist` read-only — **rebuild the frontend before `docker compose up --build`**. The backend container runs `alembic upgrade head` then uvicorn; locally you must run Alembic yourself.
- New backend env vars go in `app/core/config.py` (Pydantic Settings) **and** `.env.example`.

## Domain rules (critical, easy to miss)

- **Never put video URLs (`.mp4`/`.webm`) in `<img>` or CSS `background-image`** — browsers block them and the CDNs 429. Use `preview_url`/`sample_url` for grids/thumbnails; render video only in `<video>`.
- **Never add `<meta name="referrer" content="no-referrer">` to `frontend/index.html`** — booru CDNs require the referrer; stripping it causes 403/CORB on media.
- Danbooru free accounts allow only **2 tags** per query: the provider strips extra tags and filters them locally in Python.
- `order:score` on Danbooru needs a score floor (provider injects e.g. `score:>=100`) or Danbooru returns 500s on timeout.
- Rule34 requires `RULE34_USER_ID` **and** `RULE34_API_KEY`; guest mode forces `rating:general` regardless of user filters.
- Providers live in `backend/app/services/booru/` (one file per site, `BaseBooru` ABC with a `normalize_post()` contract); multi-site fan-out/dedup is in `booru_client.py`.

## Conventions

- Tests colocated: `foo.ts` → `foo.test.ts` beside it; grouped suites under `frontend/src/tests/`. Backend mirrors this (`app/**/test_*.py`). Vitest only — never introduce Jest.
- Frontend uses **npm** (`package-lock.json`), not pnpm.
- All UI text goes through the EN/RU localization (`stores/lang`); no hardcoded user-facing strings.
- `.agents/booruhub.md` and `.agents/rules/booruhub.md` contain a detailed repo map and rules but are **gitignored** (local-only). This file is the committed source of truth.

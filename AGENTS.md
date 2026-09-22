# Operon

Financial operations intelligence platform. Monorepo with two independent apps:

- `backend/` — Python + FastAPI + DuckDB. See `backend/README.md`.
- `frontend/` — Next.js + TypeScript. See `frontend/README.md` and
  `frontend/AGENTS.md` (auto-managed by `next dev`; regenerated there, not here).

They communicate only over HTTP (`NEXT_PUBLIC_API_BASE_URL` -> FastAPI's `/api/*`).
There is no root-level build step or shared `node_modules`/`.venv` — set up and
run each app from its own directory.

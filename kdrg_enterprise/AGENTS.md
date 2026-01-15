# AGENTS guide for kdrg_enterprise
## Scope and audience
- Purpose: give coding agents the repo-specific rules and commands.
- Scope: applies repo-wide until more specific AGENTS.md appear.
- Repo status: not a git repo; keep changes minimal and documented.
- Missing Cursor/Copilot rules found: none present in repo.
- Languages: Python (FastAPI), TypeScript/React (Vite).
- Data dirs: backend/data, backend/logs, backend/data/uploads, backend/data/exports.
- Keep secrets out of the repo; use .env for overrides.
- Prefer incremental, minimal changes aligned to existing style.

## Repository map (paths relative to repo root)
- backend/: FastAPI app, config, services, models, data dirs.
- backend/api/: route modules (auth, patients, analysis, comparison, etc.).
- backend/services/: business logic, parsers, comparison utilities.
- backend/models/: ORM models and schemas if added.
- backend/utils/: helpers used across services.
- start.sh: orchestrates backend venv install + uvicorn + frontend dev server.
- frontend/: Vite React TS app, Tailwind config, axios/react-query utilities.
- frontend/src/pages|components|hooks|services|utils contain UI logic.
- test_feedback_parser.py / test_comparison_service.py: sample scripts that exercise backend services.
- .env.example: environment template for settings.
- logs/, data/: runtime outputs and sample spreadsheets.

## API keys
- 신청 필요: OpenAI, Google Gemini API 키.
- OpenAI 키 발급: https://platform.openai.com/api-keys 에서 로그인 후 생성.
- Gemini 키 발급: https://aistudio.google.com/app/apikey 에서 프로젝트 선택 후 생성.
- 설정: `.env`에 `OPENAI_API_KEY`, `GEMINI_API_KEY` 값을 넣고 커밋 금지.
- 키는 환경변수/시크릿 관리 도구로만 사용하고 로그에 남기지 말 것.

## Environment setup
- Python: use 3.10+ recommended; create venv in backend (`python -m venv backend/venv`).
- Activate venv: `source backend/venv/bin/activate`.
- Install deps: `pip install -r backend/requirements.txt`.
- Optional dev tools: install pytest/ruff/black if needed (not bundled).
- Node: use Node 18+; `cd frontend && npm install`.
- Vite dev server port defaults to 3001 proxying to backend 8081.
- Ensure sample data paths exist: backend/data/, backend/logs/.
- Set env via .env (copy .env.example).
- On first run, execute `./start.sh` from repo root for combined setup.

## Backend run/build commands
- Dev server: `cd backend && source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8081 --reload`.
- Prod-style (no reload): omit `--reload`; configure via env.
- Start script: `./start.sh` boots backend + frontend concurrently.
- Data/log directories are created automatically by config and start.sh.
- API docs: `http://localhost:8081/api/docs` (OpenAPI), redoc at `/api/redoc`.
- Health: `GET http://localhost:8081/health`.
- Export `PYTHONPATH=backend` when running tools from repo root.
- Settings managed via `backend/config.py` using pydantic BaseSettings.
- Adjust ports with `APP_PORT` env for backend, `FRONTEND_PORT` for frontend dev server.

## Backend testing guidance
- No pytest config shipped; quickest check: `python test_feedback_parser.py`.
- Another sample: `python test_comparison_service.py`.
- Both expect backend on PYTHONPATH and sample spreadsheets in `data/`.
- To use pytest (optional): `pip install pytest` then `python -m pytest test_feedback_parser.py -k test_parser`.
- Single test via pytest pattern: `python -m pytest test_comparison_service.py -k mismatch` after installing pytest.
- For FastAPI routes, prefer `pytest` with `httpx.AsyncClient`; add tests under `backend/tests/`.
- Avoid asserting print output; prefer structured assertions.
- Keep tests deterministic; seed random generators if added.
- Mock external APIs (HIRA/OpenAI) via httpx_mock or monkeypatch.

## Frontend run/build commands
- Dev server: `cd frontend && npm run dev -- --host --port 3001`.
- Build: `cd frontend && npm run build` (runs `tsc` then `vite build`).
- Preview built assets: `cd frontend && npm run preview -- --host --port 4173`.
- No lint/test scripts defined; add `npm run lint` only if you configure ESLint.
- Tailwind CLI driven by `tailwind.config.js` and `postcss.config.js`.
- Aliases: import via `@/` per `tsconfig.json`.
- Keep `node_modules` out of patches.
- Vite proxy forwards `/api` to backend 8081; adjust in `vite.config.ts` if ports change.

## General coding style
- Prefer readability over brevity; follow existing patterns in touched files.
- Use explicit types; avoid `any` in TS and `typing.Any` in Python unless necessary.
- Keep functions small and cohesive; extract helpers to `utils`/`services`.
- Avoid global state; use dependency injection or context where appropriate.
- Write docstrings/comments in Korean when user-facing strings are Korean; keep concise.
- Do not add license headers.
- Keep new dependencies minimal; justify additions in PR text.
- Maintain consistent naming: snake_case in Python, camelCase/PascalCase in TSX.

## Python style (backend)
- Follow PEP 8; line length 120 max preferred.
- Imports: stdlib, third-party, local; separate with blank lines; no wildcard imports.
- Use type hints everywhere; prefer `pydantic` models for request/response schemas.
- Use `pathlib.Path` for file paths when adding new code; keep existing `os.path` if already used.
- Avoid mutable default args; use `Optional[...]` with `None` defaults.
- Use f-strings for formatting; avoid string concatenation.
- Prefer `logging` over `print`; reuse module-level `logger`.
- Use `async` endpoints where IO-bound; avoid blocking calls inside async functions.
- Encapsulate business logic in `services/`; keep routers thin.
- Validate external inputs early (file extensions, sizes, required columns).
- Handle missing env values gracefully; surface actionable error messages.
- When raising HTTPException, use localized messages and appropriate status codes.
- Use dependency overrides for auth in tests rather than stubbing global state.
- JWT/crypto keys must come from env; do not hardcode new secrets.

## FastAPI conventions
- Define routers in `api/*.py` with tags and prefixes; register in `main.py`.
- Use `Depends` for auth/validation; keep `require_admin` for admin-only routes.
- Return pydantic models or typed dicts; avoid naked lists without schema.
- Set response models when adding new endpoints to keep OpenAPI accurate.
- Use background tasks for long-running work instead of blocking requests.
- Apply CORS updates in `main.py` via settings.ALLOWED_ORIGINS.
- Add middleware sparingly; ensure ordering does not break auth.
- Keep OpenAPI paths under `/api/*`; leave root health endpoints minimal.

## Pydantic & validation
- Use `BaseModel` for request/response; leverage validators for normalization.
- Prefer `field_validator` over manual checks post-init.
- For settings, extend `Settings` in `config.py`; new env keys should include defaults and type hints.
- Keep privacy toggles (mask/encrypt) respected in new services.
- When reading Excel/CSV, sanitize column names and handle missing values.
- Return consistent shapes: include `success` flags only if pattern already exists.
- Avoid leaking sensitive data in logs or responses.

## Logging and error handling
- Use module-level `logger = logging.getLogger(__name__)`; configure via `logging.basicConfig` already in main.py.
- Log high-level events (start, completion, counts), not raw payloads.
- Catch broad exceptions only at boundaries; rethrow with context-specific HTTPException.
- Include request identifiers or filenames in error logs for traceability.
- Avoid swallowing exceptions silently; return user-friendly Korean messages.
- For batch operations, collect per-record errors and summarize.
- Prefer structured errors (code, message, detail) when expanding API.

## TypeScript/React style
- Strict mode enabled; satisfy the compiler instead of using `as any`.
- Components as functions; use PascalCase for components, camelCase for hooks/utilities.
- Keep hooks pure; avoid side effects outside `useEffect`.
- Derive state from props/query data rather than duplicating.
- Favor React Query for data fetching; handle loading/error/empty states explicitly.
- Use `useAuth` context for auth checks; guard routes via `PrivateRoute`.
- Use `clsx` for conditional classnames; keep Tailwind classes sorted by layout→spacing→color.
- Avoid inline functions in JSX when easily memoizable; consider `useCallback`/`useMemo` for heavy work.
- Prefer `axios` instance in `services/api` (if present) for base URL and auth headers.
- Keep routing under `AppRoutes` consistent; add new pages under `src/pages`.
- Avoid storing tokens outside localStorage; clear on logout.
- Handle nullability explicitly when using optional chaining.
- Use `aria-` attributes for form controls and buttons.
- Keep components small; move complex tables/charts into subcomponents.

## Styling (Tailwind/CSS)
- Tailwind configured; prefer utility classes over custom CSS when feasible.
- Place shared styles in `src/styles`; avoid global overrides unless necessary.
- Maintain consistent spacing scale; match existing layouts.
- Dark mode not present; avoid adding unless requested.
- For icons, use `lucide-react`; keep size/color props configurable.
- For charts, use Recharts; keep data keys typed.

## Data and files
- Sample Excel paths used in tests: `data/sample_claim_data.xlsx`, `data/sample_review_result.xlsx`.
- Keep uploads/exports under `backend/data/uploads` and `backend/data/exports`.
- Do not commit generated logs or export files.
- When adding new data parsers, enforce row limits via settings (MAX_UPLOAD_ROWS, etc.).
- Use UTF-8 encoding by default; handle Korean strings safely.
- Respect privacy masks before returning patient identifiers.

## Git and workflow
- Keep changes minimal; avoid renaming files without necessity.
- Document new commands in this file if you add scripts.
- Prefer descriptive commit messages focused on intent (if repo gains git).
- Run targeted checks (tests/build) for files you touch.
- Avoid editing `node_modules` or `venv`; keep diffs clean.

## Cursor/Copilot rules
- No Cursor rules (.cursor/rules, .cursorrules) found.
- No Copilot instructions (.github/copilot-instructions.md) found.

## Final reminders
- Keep AGENTS.md updated when adding tooling or scripts.
- When unsure, follow existing patterns and prefer explicitness.

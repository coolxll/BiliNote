# Repository Guidelines

## Project Structure & Module Organization

- `backend/` contains the FastAPI service. Application code lives in `backend/app/`, entrypoint configuration is in `backend/main.py`, and tests are in `backend/tests/`.
- `BillNote_frontend/` is the React 19, TypeScript, Vite, Tailwind, and Tauri client. Put UI code under `src/`, static assets under `public/` or `src/assets/`, and desktop-specific code under `src-tauri/`.
- `BillNote_extension/` is the Vue/Vite browser extension. Source is under `src/`; browser tests are under `e2e/`.
- Deployment and operational files live in `deploy/`, `scripts/`, `nginx/`, and the root Docker Compose files. Documentation belongs in `docs/` or the relevant module README.

## Build, Test, and Development Commands

- `run.bat`: start the backend on `8483` and frontend on `3015` using the repository virtual environment.
- `cd backend; ..\.venv\Scripts\python.exe main.py`: run only the FastAPI backend.
- `cd BillNote_frontend; npm run dev`: start the Vite frontend.
- `cd BillNote_frontend; npm run build`: create the production Vite bundle.
- `cd BillNote_frontend; npm run lint`: run ESLint across the frontend.
- `cd backend; ..\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`: run backend tests.
- `cd BillNote_extension; pnpm test` or `pnpm test:e2e`: run Vitest or Playwright extension tests.

## Coding Style & Naming Conventions

Use four spaces for Python and two spaces for TypeScript/TSX. Frontend formatting follows `.prettierrc`: no semicolons, single quotes, 100-character lines, LF endings, and Tailwind class sorting. Use `PascalCase` for React/Vue components, `camelCase` for functions and variables, and `snake_case` for Python modules and tests. Keep changes scoped to the owning module; avoid unrelated refactors.

## Testing Guidelines

Name Python tests `test_*.py` and test methods `test_*`. Extension unit tests use Vitest; end-to-end tests use Playwright. Add focused regression tests for bug fixes and broader coverage for shared APIs or user workflows. For UI changes, verify responsive layouts and include manual reproduction steps.

## Commit & Pull Request Guidelines

Commits and PR titles follow Conventional Commits: `type(scope): subject`, for example `fix(frontend): preserve podcast filters`. Allowed types include `feat`, `fix`, `docs`, `test`, `refactor`, `build`, `ci`, `chore`, and `ui`. Target routine work at `develop`. PRs must explain why, summarize key changes, list tests, note regression risks, link issues, and include screenshots or recordings for UI changes. Do not include `.env`, credentials, generated output, or unrelated workspace changes.

# ApexVision 3D: F1-style car engineering and damage simulator

ApexVision 3D is an interactive, browser-based engineering explorer for an **original, generic** open-wheel ground-effect race car.
You can:
- select any of 20 components on a 3D model
- read what each component does
- damage a component with a severity slider and see the damage represented on the model
- see the effect on aerodynamics, tyres, brakes, cooling and lap time, computed by a Python engineering model
- ask the AI Assistant to explain the results

> **Honesty notice.** Every performance number is **MODEL-ESTIMATED**. It comes from a simplified engineering model that
> is **not CFD** and is **not validated against any real car**. The car is not a model of any real team's car. The 3D damage
> visuals are a kinematic representation, not a deformation or fracture model. See
> [docs/simulation_methodology.md](docs/simulation_methodology.md).

## Features

| Area | What you get |
|---|---|
| 3D viewer | Procedural GLB with 20 selectable components in an original black and red showroom livery on a lit turntable; the car turns gently to follow the cursor (toggle; off when the OS asks for reduced motion); hover tooltips; exploded view; isolate, hide and show all; X-ray; perspective, front, rear, left, right and top camera presets; auto-rotate; PNG screenshot; fullscreen; one-click view reset. Browsers without GPU acceleration get a lighter scene automatically |
| Overview row | Vehicle performance card, three mini charts (downforce vs speed, tyre grip over the stint, brake temperature over a lap) and a Simulate Damage card: pick a component, damage type and level, see the backend severity-sweep estimate, then apply it to run the full simulation |
| Engineering panels | For each component: position, purpose, construction, performance share, failure modes, model parameters, related parts, and a specialised analysis table (front wing, rear wing, floor, cooling, tyres, brakes, suspension, power unit, structural) with baseline, current and Δ |
| Damage | Damage type plus a 0–100% slider (levels: healthy, minor, moderate, severe, critical); 11 preset scenarios including a combined lap-one incident; per-damage mechanism explanations; visual damage on the model |
| Simulation | Component-resolved aero (ride height, DRS, balance), tyre grip model, brake and coolant thermal ODEs with fade and power derate, quasi-steady lap simulation on an invented 5.18 km circuit, severity sweeps |
| Dashboard | 13 Plotly charts: downforce and drag vs speed, balance, lap speed trace, brake temperature, coolant by lap, tyre grip, stint lap time, lap-time impact, severity sweep, component health. Each chart has a data-table view |
| AI Assistant | Gemini, OpenAI or Groq tool calling with 6 tools. Every number in an answer is verified against tool outputs. A built-in **rule-based engine works with no API key**, so the public demo needs no keys from visitors |
| Data | PostgreSQL (Neon) through SQLAlchemy and Alembic, with an SQLite fallback for zero-setup local runs. Stores sessions, simulations, damages and reports |
| Reports | Markdown, printable HTML (save as PDF) and JSON reports; CSV export |
| Assumptions | Every model assumption can be edited in the UI and through the API |

## Architecture

```
frontend/  React 18 + TypeScript + Vite + Tailwind + Radix/shadcn-style UI + three.js / R3F / drei + Plotly + zustand
   └─ calls ──►  backend/  FastAPI + Pydantic + NumPy/SciPy/Pandas + SQLAlchemy/Alembic
                    ├─ app/simulation   engineering models (pure functions, cached)
                    ├─ app/domain       component catalogue + scenarios
                    ├─ app/ai           tools, Gemini/OpenAI providers, offline engine, numeric verifier
                    ├─ app/api/v1       REST endpoints
                    └─ app/db, reports  persistence + report generation
assets/tools/generate_car.py   procedural GLB generator  →  frontend/public/models/
docs/                          methodology, component specs, 3D asset guide
```

### REST API (`/api/v1`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/car`, `/components`, `/components/{id}`, `/scenarios` | Catalogue and model metadata |
| GET | `/vehicle/status` | Healthy car status |
| POST | `/damage/simulate` | Full coupled simulation with curves. `persist: true` stores it and creates a report |
| POST | `/aerodynamics/calculate`, `/performance/analyse`, `/simulation/compare` | Focused calculations |
| POST | `/performance/export.csv` | CSV of the current result |
| GET | `/history?session_id=`, `/reports/{id}?format=json\|md\|html` | Saved runs and reports |
| POST | `/ai/ask` | AI Assistant (rate limited) |
| GET | `/health` | Liveness check |

Interactive docs are at `http://localhost:8000/docs`.

## Run locally

Prerequisites: Python 3.11+ and Node 20+.

```bash
# backend
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt        # Windows  (macOS/Linux: .venv/bin/pip)
cp .env.example .env                                      # optional; defaults work with no edits
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m uvicorn app.main:app --reload     # http://localhost:8000

# frontend (second terminal)
cd frontend
npm ci
npm run dev                                               # http://localhost:5173
```

With no `.env`, the backend uses a local SQLite file and the offline AI engine.

### Docker

```bash
docker compose up --build        # Postgres 16 + backend :8000 + frontend :8080
```

To enable the LLM assistant locally, export `GEMINI_API_KEY`, `OPENAI_API_KEY` or `GROQ_API_KEY` in your shell first. Compose passes it
through, so it is never written to a file.

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest -q && .venv/Scripts/python -m ruff check .   # 50 tests
cd frontend && npm run typecheck && npm test                                              # 17 unit tests
cd frontend && npx playwright install chromium && npm run test:e2e                        # 8 end-to-end tests
```

The e2e run starts its own backend (SQLite, offline AI) and Vite dev server. GitHub Actions
(`.github/workflows/ci.yml`) runs:
- ruff and pytest
- Alembic migrations against a real Postgres service
- typecheck, unit tests and build
- the Playwright suite
- both Docker builds

## Deployment (Vercel + Render + Neon)

1. **Neon:** create a project and copy its connection string (`postgresql://…?sslmode=require`).
2. **Render:** create a *Blueprint* from this repository. `render.yaml` defines a Docker web service rooted at
   `backend/`, with a health check at `/health`. Set these secret environment variables in the Render dashboard (never in the repo):
   - `DATABASE_URL`: the Neon string. Migrations run automatically on start.
   - `CORS_ORIGINS`: your Vercel URL, for example `https://apexvision.vercel.app`.
   - `GEMINI_API_KEY`, `OPENAI_API_KEY` or `GROQ_API_KEY`: *optional*. Without one, the assistant uses the rule-based engine.
3. **Vercel:** import the repository with **root directory `frontend`** (framework preset Vite). Set
   `VITE_API_BASE_URL` to the Render URL, for example `https://apexvision-api.onrender.com`. `vercel.json` handles the SPA
   rewrites and asset caching.

### Environment variables

| Variable | Where | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | backend | `sqlite:///./apexvision.db` | `postgres://` and `postgresql://` URLs are normalised to psycopg |
| `CORS_ORIGINS` | backend | `http://localhost:5173,…` | Comma-separated list |
| `DATABASE_URL_UNPOOLED` | backend | unset | Neon direct connection, used only for migrations |
| `AI_PROVIDER` | backend | `auto` | `auto`, `gemini`, `openai`, `neon` or `offline` |
| `NEON_AI_GATEWAY_BASE_URL` / `NEON_AI_GATEWAY_TOKEN` / `NEON_AI_MODEL` | backend | unset / unset / `claude-haiku-4-5` | Neon AI Gateway (secret token). Needs prepaid Neon AI credits |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | backend | unset / `gemini-2.5-flash` | Secret |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | backend | unset / `gpt-4o-mini` | Secret |
| `GROQ_API_KEY` / `GROQ_MODEL` / `GROQ_FALLBACK_MODEL` | backend | unset / `openai/gpt-oss-120b` / `openai/gpt-oss-20b` | Secret key. The fallback model is tried when the main one hits the free-tier tokens-per-minute limit |
| `AI_RATE_LIMIT_PER_MINUTE` | backend | `12` | Per client IP |
| `AI_GLOBAL_RATE_LIMIT_PER_MINUTE` | backend | `60` | Across all clients; caps LLM spend even if client IPs are spoofed |
| `VITE_API_BASE_URL` | frontend build | empty (same origin) | Backend URL |

No credentials are committed. `.env*` files are git-ignored except `.env.example`, and API keys stay on the server.
The browser never sees them.

## Documentation

- [docs/simulation_methodology.md](docs/simulation_methodology.md): equations, damage transfer functions, thermal and lap models, and limits of validity
- [docs/component_specifications.md](docs/component_specifications.md): all 20 components (generated from the backend catalogue)
- [docs/3d_asset_guide.md](docs/3d_asset_guide.md): model conventions, regenerating the model, and replacing it in Blender

## Known limitations

- The engineering models are lumped and quasi-steady. They have no combined slip, no load-transfer dynamics and no gears.
  Tyre temperature is fixed within a lap. See the methodology's limits section.
- Structural damage is a scalar integrity indicator. No deformation or fracture is simulated, and the 3D effects are illustrative.
- The procedural model is a stylised concept. It has no CAD-level detail.
- The production frontend bundle is large: three.js is about 1.1 MB, and Plotly (about 4.7 MB) is lazy-loaded only for the dashboard.

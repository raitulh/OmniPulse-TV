# OmniPulse TV

**A remote-first sports intelligence companion for Fire TV.** OmniPulse combines household preference memory, an interactive tactical field, contextual AI explanations, and an optional local pose-coaching experience in one interface.

> **Honest status:** This repository is a production-oriented, runnable project foundation—not a claim that it has been deployed, security-audited, or verified on every Fire TV/Vega device. The included fixture is explicitly labelled `sample`; it is not a live match feed. Production launch requires a licensed sports-data integration, configured identity provider, deployed infrastructure, platform verification, and operational testing.

## Included

- **Backend:** FastAPI, SQLAlchemy, SQLite for local development, PostgreSQL-compatible models, JWT validation, Cognito access-token verification, household/profile preferences, viewing sessions, sample sports events, tactical data, analysis history, consent-based coach sessions, feedback, and household-data deletion.
- **AI provider boundary:** Deterministic rules are the default. Optional Amazon Bedrock explanations can be enabled by configuration; they use retrieved event context and fall back to rules on failure.
- **TV frontend:** React + TypeScript + Vite, remote-first focus navigation, household modes, X-Ray tactical field, voice adapter with typed fallback, optional browser-side MediaPipe Pose Landmarker, responsive UI, API error handling, and sample-data labels.
- **Landing page:** Separate `/landing` route in the same static frontend build.
- **Quality:** pytest API/integration tests and Vitest unit tests; Dockerfiles and Docker Compose; Alembic migration scaffolding; CI workflow.

## Visual identity

| Token | Hex | Use |
|---|---|---|
| Obsidian Black | `#0B0F14` | Main background |
| Cloud White | `#F5F7FA` | Main text |
| Electric Lime | `#C6F36B` | Active/focused items, primary CTA |
| Copper | `#B8734E` | Brand and secondary emphasis |

## Quick start — local development

Requirements: Python 3.11+ (3.12 recommended), Node.js 20+ (22 recommended), npm, and a modern browser. Camera access normally requires HTTPS or `localhost`.

### 1. Start the backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env  # PowerShell; on macOS/Linux use: cp .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://localhost:8000/docs` for the OpenAPI UI and `http://localhost:8000/health/ready` for readiness. Local development automatically creates the SQLite schema and seeds one labelled fixture.

### 2. Start the frontend

In a second terminal:

```bash
cd frontend
npm install
copy .env.example .env  # PowerShell; on macOS/Linux use: cp .env.example .env
npm run dev
```

Open `http://localhost:5173`. The local demo auth endpoint issues a short-lived local development token. This mode is intentionally for local demos only.

### 3. Start with Docker

From the repository root, after Docker Desktop is running:

```bash
docker compose up --build
```

Frontend: `http://localhost:8080` · API: `http://localhost:8000/docs`. Stop with `docker compose down`. The SQLite database is persisted under `backend/data/`.

### 4. Run tests

Backend tests (from repository root):

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest
```

Frontend tests/build (from another terminal):

```bash
cd frontend
npm install
npm test
npm run build
```

## Demo walkthrough

1. Open Watch Hub and verify the `SAMPLE DATA` label.
2. Choose Analyst Mode, Family Lounge, or Catch Me Up.
3. Open Sports X-Ray.
4. Click a player node or use arrow keys to navigate focus, then press Enter/Select or choose Analyze Player.
5. Try a command such as “Break down this play” or “Who is player 07?”.
6. Change household preferences, save them, and reload to verify persistence.
7. For Active Coach, grant explicit consent and use a supported browser camera. Camera availability, GPU support, and remote-device support vary; pose model assets must be downloaded from the configured host.

The included sports fixture and its player positions/speeds are invented sample values for deterministic UI/testing. Do not present these as official match data, live tracking, or measured athletic performance.

## Authentication and production mode

- **Local demo:** `ENVIRONMENT=development`, `DEMO_MODE=true`, with a local HS256 secret. Never use the default local secret on a public deployment.
- **Production identity:** Configure `ENVIRONMENT=production`, `DEMO_MODE=false`, `AWS_REGION`, `COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_ID`, and frontend `VITE_AUTH_MODE=cognito` plus Cognito Hosted UI configuration. Backend validation accepts Cognito RS256 access tokens, checks the issuer, `token_use=access`, and `client_id`. First-login onboarding provisions one household/profile per Cognito subject.
- Create a Cognito app client that supports authorization code grant with PKCE, without a client secret for the TV/public client. Set exact allowed callback/logout URLs. Use HTTPS in deployed environments.
- Use a managed PostgreSQL database in production. Configure `DATABASE_URL` as `postgresql+psycopg://...`; run `alembic upgrade head` as a controlled release/migration step before deploying the API. Production startup intentionally does not auto-create schema or insert demo sports fixtures.
- Restrict CORS to exact deployed origins. Use a secret manager, least-privilege IAM, TLS, API Gateway/WAF throttling, backups, alarms, and a documented deletion/retention policy.

## Optional Amazon Bedrock adapter

Set `AI_PROVIDER=bedrock`, `BEDROCK_MODEL_ID` and `AWS_REGION` in the backend environment, then grant the runtime identity permission for the selected Bedrock model. Do not place AWS credentials in `.env` committed to Git or in the frontend. If Bedrock is not configured or fails, the service returns the deterministic rules-based explanation. In all cases, the response keeps the data source type (`sample` or `provider`) visible.

The Bedrock adapter does **not** ingest live sports data. A production sports-data provider and its license/attribution rules need a separate adapter; the included database intentionally contains only the demo fixture.

## Platform limitations to verify

- Remote microphone hardware is not guaranteed to expose browser speech APIs to a web app. The frontend checks Web Speech capability and provides typed command fallback. For a real Fire TV release, integrate and test the supported platform voice path.
- Camera support is not guaranteed on every television or Fire TV device. Pose processing uses the browser-side MediaPipe task only where camera APIs, GPU/runtime capabilities, HTTPS, and model asset downloads work.
- Browser preview keyboard keys approximate directional remote input; real TV behavior must be tested on the selected hardware/official simulator.
- This application does not include licensed streaming playback, a video DRM stack, or a production live match feed.

## Repository map

```text
backend/           FastAPI API, SQLAlchemy entities, services, tests, migrations
frontend/          TV web app, landing page, design tokens and frontend tests
docs/              Architecture, API contract, security, data provenance, QA and friction logs
.github/workflows/ CI test pipeline
docker-compose.yml Local container orchestration
```

## License

MIT. See `LICENSE`. Third-party dependencies and externally loaded pose-model assets remain under their own licenses and terms.

## Verification status

See [`docs/verification-report.md`](docs/verification-report.md) for exact checks and environment limitations. The backend test suite passed in the assembly environment. A full Vite/Vitest run requires `npm install` with npm registry access; actual Fire TV remote, voice and camera behavior still requires target-platform testing.

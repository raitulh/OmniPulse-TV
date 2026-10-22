# OmniPulse TV — Architecture and Boundaries

## System boundary

OmniPulse is a companion experience for supported TV application runtimes. It does not host licensed match video or assume it owns live sports tracking. The TV frontend handles rendering, spatial remote focus, browser speech where supported, and local pose estimation where supported. FastAPI manages persistent preferences, viewing sessions, tactical fixtures, analysis history, coach sessions, derived metrics, and feedback.

## Runtime architecture

- TV web UI: static React/TypeScript build delivered over HTTPS.
- API: FastAPI modular monolith. Module boundaries: auth, household, sessions, sports, personalization, analysis, coach and feedback.
- Persistence: SQLite for local dev/test; PostgreSQL via SQLAlchemy for deployed environments.
- Identity: local HMAC-signed demo session only in development. Production path validates Cognito RS256 access tokens using Cognito JWKS and provisions a household on first login.
- AI: rules-based provider by default; optional Bedrock Converse adapter. Provider failures degrade to deterministic rules, with provider/source labels retained.
- Pose model: MediaPipe Pose Landmarker runs in the browser. Backend accepts derived metrics only and has no raw video/audio endpoint.
- Operations: Docker, Alembic, CloudWatch-compatible structured logs, health endpoints and GitHub Actions test pipeline.

## Trust boundaries

1. Browser input is untrusted. API requests receive Pydantic validation and ownership checks.
2. AI-generated text is not a source of verified sports facts. Player nodes and IDs come from retrieved event records.
3. Sample fixtures are always returned with `source_type=sample`.
4. Cognito identity is validated by signature, issuer, token-use and app-client claims before database ownership is checked.
5. Camera processing requires explicit user consent and runs locally; only derived metrics are sent to the backend.

## Production decision gates

Before real users: deploy Cognito and PostgreSQL; configure migration and backup jobs; add a licensed sports-data adapter with source timestamps and provider IDs; set quotas/throttling; perform privacy/legal review; and run end-to-end tests on the actual target Fire TV/WebView.

## Scale-out triggers

Do not split services just because the system has different modules. Split sports ingestion when provider ingestion volume/back-pressure is measurable; move long AI jobs to a queue when response latency or concurrency requires it; introduce cache only after observing repeat reads or database load; and add WebSocket/SSE only if the selected provider's live update requirements justify persistent connections.

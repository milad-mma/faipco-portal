# v7 — Event-driven PWA release update (test)

Base: `FAIPCO-Portal-PWA-Session-Recovery-v6-Test.zip`.

- New authenticated release-only WebSocket at `/api/v1/system/release-ws`, separate from attendance GPS/presence.
- PostgreSQL LISTEN/NOTIFY for fanout to all FastAPI workers, with active-build replay after reconnect.
- Installer builds Vite in staging and activates the release only after DB migrations, backend/Nginx setup and health check pass. Failed builds never touch the active frontend.
- New release notification is shown only after Service Worker reaches `waiting`. Browser never automatically reloads in the middle of editing a form.
- Legacy 30s `version.json` fetch timer and 60s SW update timer removed; a single SW check remains for tab focus, visibility and reconnect.
- Current RBAC, authentication restore, HR/letter/insurance/payroll/business logic and Android assetlinks integration preserved. No Alembic changes.
- Unit tests and release activation tests added.

Limitations: This candidate is not a substitute for Android TWA, PostgreSQL LISTEN/NOTIFY, reverse proxy and concurrency testing on the actual test server. There is no production Vite build in the packaging environment (npm packages unavailable).

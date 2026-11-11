# FAIPCO PWA release notifications — v7 (test-server release)

## Scope

This change is deliberately confined to **PWA frontend publication and update
notifications**. The attendance GPS presence WebSocket, HR, careers,
notifications, payroll, letters, insurance, auth refresh rules and all RBAC
permission definitions are unchanged. No database migration or new NPM/Python
dependency is required (`asyncpg` was already installed).

## New sequence

1. `install.sh` acquires a non-blocking host-wide file lock.
2. The existing Git/database/backend/permission/Nginx stages run as before.
3. Vite builds to `frontend/releases/.staging.*`, NEVER into the live `dist`.
4. `scripts/activate_frontend_release.py` validates `index.html`, `sw.js`,
   `version.json`, JS assets, and carries over the old `/.well-known` assets.
5. The previous `/assets/` content is kept for open clients with older JS.
6. Once the backend health check and all installation stages succeed, `dist`
   changes to a symlink pointing at `frontend/releases/build-<build-id>`.
   First-time migration from the old `dist` directory involves two filesystem
   renames (a brief, non-atomic initial migration); subsequent symlink changes
   use an atomic `os.replace()` operation.
7. The installer reapplies current brand title + Android assetlinks settings;
   then `scripts/publish_release_event.py` invokes PostgreSQL `pg_notify`.
8. All FastAPI workers listen on `faipco_frontend_published` using one
   asyncpg connection *per worker*, NOT one PostgreSQL connection per client.
9. Authenticated portal clients receive `{type:"portal.release",build:"..."}`
   on a dedicated WebSocket `/api/v1/system/release-ws` (separate from GPS).
10. This starts `ServiceWorkerRegistration.update()`; the update Snackbar
    appears ONLY when `registration.waiting` exists and the previous worker
    controls the page. Reload remains user-controlled.

## Catch-up / failure handling

- If PostgreSQL `NOTIFY` is missed while Android is backgrounded, reconnecting
  WebSocket clients receive the **active** build from `dist/version.json`.
- The tab also checks its SW when it becomes visible, receives focus or comes
  online. There is **no 30-second HTTP polling or 60-second SW polling**.
- WebSocket handshake uses a session access token as a subprotocol rather than
  a URL query, validates the same user status, password-change and session
  revocation checks, and never broadcasts private employee data.
- The dedicated channel is for **authenticated tabs**. Public login/careers
  pages retain standard browser SW checks on navigation/focus; no anonymous
  long-lived WebSocket is exposed to the internet.
- On initial upgrade from v6, open v6 tabs still execute their OLD polling
  script until the v7 worker is activated. From v7 onward the timer is gone.
- WebSocket failure is non-fatal to the portal; on focus/reconnect, the Service
  Worker checks for a new version. No old caches are deleted to update.
- If a Build, migration, service check or Nginx step fails, the release is not
  activated and no notification is sent. If the optional Postgres broadcast
  fails after successful activation, the installer logs a warning and sessions
  can still catch up on the next reconnection/focus.

## Rollback (test server)

An earlier release is kept at `frontend/releases/legacy-*` (first upgrade) or
`frontend/releases/build-*` (later upgrades). Switching the symlink back must
be coordinated with backend and database schema compatibility; NEVER stamp or
revert Alembic blindly. On a test machine, capture the target first:

```bash
readlink -f /var/www/html/frontend/dist
ls -lah /var/www/html/frontend/releases/
```

Use the standard repository/deployment rollback process for restoring a
compatible backend+frontend pair. For initial tests, do not modify data.

## Tests and acceptance criteria

- Check output of `python backend/tests/api_snapshot.py` for zero removed APIs
  and one deliberate added WS route.
- `cd frontend && npm run test:unit` (node-only tests are network independent).
- `pytest -q backend/tests/test_release_activation.py`.
- On Android TWA: deployment-in-progress never shows the update prompt.
- After deployment, one prompt appears only after the new Worker is waiting.
- Clicking load preserves the authenticated session and current route.
- Background/reopen recovers the missed release; invalid session still blocks.
- Existing legacy source ZIP (v6) should be held for rollback.

**Not yet validated here:** production Vite build (no npm registry access in
this environment), live PostgreSQL LISTEN/NOTIFY, a real Nginx release swap,
Android TWA or a load test with 1000 websocket clients. Test on the TEST server
before deploying to production.

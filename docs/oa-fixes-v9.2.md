# FAIPCO Portal — Office Automation Reliability & Layout Fixes (v9.2 test)

**Base:** full FAIPCO Portal v9.1; intended scope: office automation only, with backwards-compatible extensions to two shared file/push services. No Alembic migration. Do not deploy directly to production without integration/Android tests.

## Correctness and safety

1. **No stale letter submission:** compose now requires a successful final draft save and waits for pending recipient, attachment and approval-path writes before send/submit. Errors block submission. Server rejects visually empty HTML.
2. **Editing conflict:** draft save locks letter row before comparing optimistic `row_version` to serialize simultaneous saves. The editor offers a local text backup on HTTP 409, plus exit warnings on edits.
3. **Approval history retained:** returning/withdrawing a submitted letter creates an editable successor version instead of overwriting submitted text/hash. Historical attachment rows and shared file contents are preserved when current-draft attachments are removed or the draft discarded. Approval/access policy unchanged.
4. **Atomic attachment transaction:** attachment upload no longer commits before binding the file to the letter, so the draft row lock is retained until the attachment transaction completes. Other callers still use the prior default behavior of `OaFileService.upload`.
5. **Notification retries:** OA notification logs are no longer created before successful send; advisory transaction locks prevent concurrent workers sending the same notification key. `PushService.notify_users` has an optional `return_stats` flag; other callers keep their existing signature/return behavior. **Limitation:** this is not a durable outbox, so worker crashes between commit and task scheduling still require a proper queued-delivery design. Partially delivered batches may be retried; duplicate device notification remains possible.
6. **Confidential metadata:** inaccessible related letters no longer expose a `sent_at` timestamp.
7. **Recipient finder:** server-side pagination (50 per page), total count and late-response filtering for person searches; selected recipients persist across pages.
8. **Template preview:** unsaved HTML is passed through a restrictive, client-side allowlist before inserting into live preview; backend sanitizer remains authoritative. Template switch warns if form has unsaved changes.
9. **Due dates:** Tehran calendar-day conversion independent of phone timezone; existing API shape unchanged.

## UI/UX, without redesign

- Cartable cards and tabs use focusable, semantic MUI action controls.
- Long letter subjects, sender names, recipient chips and workflow names ellipsize/clamp within fixed-width flex/grid slots, with tooltip/title for full names.
- Action buttons stay in predictable independent areas; compose action bar uses responsive grid with save indicator on a separate mobile row.
- Draft list shows long titles in dedicated heading space, metadata and chips on separate lines.
- Letter view separates a title line from the action toolbar.
- Loading states for attachment/recipient mutations prevent premature send. Search results from a superseded request cannot overwrite newer results.
- Fixed automatic manager signature name tooltip in approval path.

## Explicitly unchanged / unresolved

- All non-OA modules, RBAC, existing confidentiality policy, whether Super Admin may open secret letters, template authorization scope, API routing contracts, database migrations, GPS/presence, existing PWA update and recruitment flow were not intentionally changed.
- Archive access grants, deputy workbasket, external incoming/outgoing registry, parallel approvals, advanced reports and reminder automation are new features, *not* included.
- Recipient records are currently letter-level (not per-version); older approval rounds keep original body/hash and attachments, but per-round recipient snapshots are not newly modeled.
- Browser-based print pagination, Android UI, real PostgreSQL concurrency, SMTP/push delivery and tests with 1000 concurrent clients **not verified** here.
- Full frontend production build was **not verified** here: `vite` / local `node_modules` unavailable. No deployment to a test or production server was performed.

## QA (local environment)

- Existing OA rule/backend tests: 35 passed, 2 Pillow deprecation warnings. Additional service-level regression file skipped here because PostgreSQL runtime modules not installed.
- Frontend Node unit tests: 41 passed (including timezone tests).
- Changed JS/JSX syntax validated with TypeScript parser; changed Python syntax compiled without importing app runtime.
- Git diff checked; full v9.1 baseline archive preserved plus intended scope changes.

## Acceptance checks on `faipco-portal-srv`

1. Edit subject/body immediately before pressing send; disconnect network; ensure no older revision is dispatched.
2. Submit through an approval path; return for correction; check prior submitted body, its hash and attachment files remain intact after modifying/removing new draft attachments.
3. Save the same draft from two tabs concurrently; one succeeds and the other receives 409, with copyable local text.
4. Upload/remove large attachments while pressing send; ensure blocking until upload finishes.
5. Verify cartable/draft/detail/header at phone widths 320/375/414px and desktop 768/1024/1440px with 300-character subjects, long staff names and RTL text.
6. Verify printing multi-page letters, template HTML preview and XSS rejection using internal test data.
7. Verify independent permissions (normal/confidential), referral, secretariat and return/cancel flows; no changes in payroll, insurance, careers, HR profile, GPS and PWA update flows.

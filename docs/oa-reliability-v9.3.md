# FAIPCO Portal v9.3 — Office Automation Reliability / History / UI (TEST ONLY)

**Base:** FAIPCO Portal v9.2.1 (Cartable Tab Font Fix). **Do not deploy directly to production.**

## Implemented

1. Immutable round evidence for newly frozen/submitted letter versions:
   - `oa_letter_versions.recipients_snapshot` stores role, employee identifier, name, position, department, selection type and order at the time of approval submission / direct dispatch.
   - `oa_letter_versions.approval_plan_snapshot` records the approved routing plan for the round, including the automatic principal signature stage.
   - Old versions are deliberately left NULL; historical recipients cannot be truthfully reconstructed from current recipients. Text, content hash and historical attachments remain preserved by v9.2.
   - Letter author or named principal/sender (only while still explicitly authorized to view the letter) can inspect previous frozen/submitted versions through the new read-only history UI/API. All other recipients see only the current letter; historical data never grants access.
2. Transactional, durable office-automation push queue:
   - New `oa_notification_outbox` is created by Alembic revision **152**, directly following **151**.
   - Push intents are inserted in the *same database transaction* as OA sends, referrals, approvals, cancellations, returns and transfers. If the OA change rolls back, the outbox events roll back too.
   - Existing BackgroundTasks now kick the outbox processor instead of sending unsaved, in-memory events. A scheduler job runs every 30 seconds to retry pending events after restart/network failure.
   - `FOR UPDATE SKIP LOCKED` permits multiple FastAPI workers without double-claiming an outbox row. Retries have exponential backoff, max 10; terminal `failed` events remain observable for manual intervention.
   - Existing `oa_notification_log` keys prevent re-sending legacy events; a missing Push subscription is marked `skipped`, since no device can be notified. Pending events are still visible as letters in authenticated cartable.
   - **Delivery model is at least once, not exactly once:** if a worker crashes after the push service accepts the message but before the DB commit, retry may produce a duplicate on a device. Partial delivery can also duplicate successful device sends. No new permissions or push payload content for confidential letters.
3. Draft editor improvements:
   - A save that finishes after newer keystrokes no longer claims that the latest text was saved or allows immediate send. Displays a retryable error instead.
   - Retry button for failed saves, a responsive confirmation text, stable heading.
4. UI stability:
   - Letter metadata/status chips and action buttons now occupy independent grid areas (mobile stacks; desktop separate areas). Long titles are constrained to the title area.
   - Approval-path toolbar and steps preserve the buttons' width and inherit the portal's font. Long names are truncated within their own space.
   - A read-only version-history dialog is available to authorized authors/principals when more than one frozen/submitted version exists.
   - The v9.2.1 Vazirmatn cartable-tab fix remains unchanged.
5. Fixed a duplicated plan-cleanup loop in `oa_approval_service.submit` inherited from the old code that could delete the same planned manager stage twice.

## Database migration / rollback

`database/migrations/versions/152_oa_history_outbox.py` is **additive**. It adds two nullable JSON columns and one outbox table; no existing OA letter/recipient data is deleted or rewritten. Prior to installation confirm the live migration HEAD is 151 and back up the DB, then run the existing installer/migration process. Check the migration completes and the outbox table exists *before* bringing up v9.3 workers.

**Do not roll back to v9.2.1 binaries without planning for undelivered v9.3 outbox events.** To roll back code, ensure the queue is drained or explicitly documented; avoid auto-running `downgrade()` on a production database as this deletes pending records.

## Tests performed in this environment

- Base OA pure-rule/backend test suite: 35 passed.
- New snapshot unit tests: 2 passed.
- Frontend Node unit tests: 41 passed.
- Python compilation for changed modules and migration: passed.
- TypeScript parser check on changed JS/JSX: passed.
- Full backend test suite collection is blocked by missing environment config/dependencies (`DATABASE_URL`, `SECRET_KEY`, `DB_CREDENTIALS_ENCRYPTION_KEY`, `asyncpg`). This is an environment limit, not a pass.
- No PostgreSQL service, browser-based visual QA, actual Android app test, Push provider test, full Vite build or deployment available in this environment.

## Required acceptance on `faipco-portal-srv`

1. **Before install**: full DB backup; confirm Alembic HEAD=151; note number of OA letters, OA versions and draft counts; install revision 152.
2. **History**: create a draft with 2 recipients and 1 attachment, submit for approval, return for changes, alter recipients/body/attachments, submit again. Verify `oa_letter_versions` contains immutable snapshots for both rounds and older body/attachments are still retrievable. Test that another authorized recipient cannot open the author's historical versions.
3. **Push queue**: stop the Push provider/network, create a letter and verify the committed `oa_notification_outbox` row is `pending` with attempts increasing (not lost after backend restart). Restore network and verify `sent` or `skipped`; use multiple workers to check claim locking.
4. **Send correctness**: edit text during an in-flight save, press send, verify the newest text is not silently omitted; test broken connection and retry button; test two concurrent editors (one gets 409).
5. **Presentation**: 300-character subject, 200-character names, lengthy attachment filenames, RTL/Persian digits, 320/375/414/768/1024/1440px, light and dark themes. Confirm cartable tabs retain Vazirmatn and button groups stay in place.
6. **Non-OA regression**: verify login/recovery, profile photos, notices, payroll print, Karaweb shifts, insurance, recruitment, GPS/presence, PWA update and cache refresh. No non-OA feature was deliberately altered.
7. **Monitoring** (read-only SQL):

```sql
SELECT status, count(*) FROM oa_notification_outbox GROUP BY status ORDER BY status;
SELECT count(*) AS saved_version_snapshots FROM oa_letter_versions WHERE recipients_snapshot IS NOT NULL;
SELECT version_no, status, recipients_snapshot IS NOT NULL AS has_recipients,
       approval_plan_snapshot IS NOT NULL AS has_approval_path
  FROM oa_letter_versions WHERE letter_id = :letter_id ORDER BY version_no;
```

## Deliberately out of scope

- Access-grant archives, full secretariat registry for incoming/outgoing letters, deputy workbasket, parallel approval, Super Admin confidentiality policy and organization-wide template authorization.
- Automatic browser history blocking in a plain `BrowserRouter` (existing link/beforeunload warnings remain; unsupported navigation APIs were intentionally not introduced).
- Delivery auditing of *individual* Push subscriptions: provider outcomes are currently aggregated by user. A receipt/acknowledgment protocol would be needed to prove the message was seen, not only accepted by a Push provider.

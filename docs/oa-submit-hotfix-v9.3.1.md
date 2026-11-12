# FAIPCO Portal v9.3.1 — Office Automation Submit Hotfix

## Confirmed incident

- Route: `POST /api/v1/automation/drafts/40/submit`
- Error: `NameError: name 'planned' is not defined`
- Tracking code: `5F48D2` (also repeated with other tracking codes)
- Root cause: A refactor in v9.3 removed the assignment of `planned`, optimistic version check, and obsolete explicit-principal step cleanup from `OaApprovalService.submit` while leaving references to `planned`.
- Failure point occurs **before** changes to the letter status, version hash, approval tasks or dispatch. The failed attempts in this traceback should not have dispatched the letter; verify its actual status on the test server before retry.

## Fix

In `backend/app/services/oa_approval_service.py`:

1. Restore `letter.row_version != row_version` check (HTTP 409 conflict).
2. Restore fetching approval steps using `await self._planned(letter)`.
3. Remove a duplicate explicit principal approval step when principal signature is already appended automatically, then renumber the remaining stages.
4. Preserve v9.3 snapshots (`recipients_snapshot` and `approval_plan_snapshot`) and transaction behavior.

No changes to other modules, no new database migration. The v9.3 `152` migration is still required if upgrading from an older release; v9.3.1 itself introduces none.

## Automated tests

Added `backend/tests/test_oa_submit_regression_v931.py`, covering:

- one-approver submission all the way to commit and version snapshots;
- stale row-version rejection;
- empty approval path with user-facing error;
- automatic principal signature without duplicate;
- idempotent retry of a letter already in approval.

Run from the project root:

```bash
PYTHONPATH=backend python -m pytest -q backend/tests/test_oa_*
```

Observed in the available environment: **42 passed, 1 skipped**. The skipped existing test requires production dependencies / database environment. No live PostgreSQL, server, push or browser integration test has been run.

## Staging smoke test

1. Back up v9.3 deployment, then apply v9.3.1 to the **test server first**.
2. Restart the actual Backend service/processes after code replacement (use the service name configured on that server).
3. Open draft `40` and verify it remains `draft`. For a one-approver path, select a valid active employee and submit again.
4. Expected: HTTP success, `in_approval` state, first approval task in approver's cartable, no `NameError`.
5. Repeat with an `on behalf of` letter: manager signing step must appear only once, at the end.
6. Test a stale draft in two tabs: second submit must report a conflict and not send outdated content.
7. If there is any further 500 error, share the new traceback and tracking code. Do not repeatedly submit a draft without checking its current status.

This hotfix corrects the proven `planned` regression; it is not a claim that unrelated server issues or all workflow cases are fixed.

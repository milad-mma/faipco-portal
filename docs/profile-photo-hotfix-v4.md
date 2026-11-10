# FAIPCO — Profile / Birthday Photo Recovery v4 (test only)

Base: `FAIPCO-v3-Profile-Photo-Fix.zip` (includes careers, migration 150/151 and shift-calendar hotfix).

## Changed files
- `frontend/src/api/employees.js`: keep optional AbortSignal for profile photo and forward it for birthday-photo too.
- `backend/app/sync_engine/sync_service.py`: only update thumbnails explicitly returned as non-empty bytes; never clear existing PostgreSQL photos because a row or image is absent/NULL. This is a conservative safety behavior; intentional deletion in Karavab no longer auto-clears a portal photo.
- `frontend/tests/profile-photo-api.test.mjs`: add birthday photo signal regression.
- `backend/tests/test_photo_sync_safety.py`: isolated regression for empty/NULL/partial responses.

## Test deployment checklist
1. Back up PostgreSQL, uploads, and deployment configuration. Test server only.
2. Deploy full ZIP with usual application procedure; no new Alembic migration was added.
3. Build/deploy frontend with your existing deployment script; stale browser bundles may require a hard reload.
4. Visit personal dashboard. Inspect Network for `/api/v1/employees/<id>/photo-thumbnail` (200 with image is success; 404 indicates no saved thumbnail, 401/403 access, 500 backend failure).
5. Verify birthday list separately using `/api/v1/employees/birthday-photo/<id>` and appropriate permissions.
6. If thumbnail was previously erased in PostgreSQL, perform an **authorized test-site** personnel sync AFTER backing up DB and confirming the EmployeeMapping photo columns and Karavab connection. This hotfix will restore only those employee photos whose source returns non-empty bytes; it will no longer delete stored photos for missing/NULL source images.
7. Monitor the sync log for warnings and confirm the correct employee/site codes and `has_photo` in `/auth/me`.

## Scope and limitations
- Source/API unit tests passed; actual database-backed sync, production frontend build and deployment-dependent print/upload flows are NOT confirmed in this environment.
- No new migrations. No modifications to shift logic, career module or existing file content outside the changed files above.
- Do not treat missing source data as an instruction to delete personal photos. Intentional deletion should be handled separately with audit/confirmation.

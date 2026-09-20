# Checkpoint 2 progress: identity and tenant foundation

Historical checkpoint snapshot. UPDATE 2026-09-19: PostgreSQL authentication and migration verification are now successful. The implementation has advanced substantially; see V1_PROGRESS.md for current status. The earlier blocked results below are retained as history. Neither PILOT CORE READY nor V1 ready has been declared.

## Preserved state

- Continued the existing develop branch and uncommitted Checkpoint 1 work.
- No regeneration, new repository, commits, pushes, or main-branch changes.
- All eight locked DOCX files match their HEAD blobs byte-for-byte.
- Latest owner instruction authorizes continuous V1 development; older approval pauses are superseded.

## Implemented initial foundation

- Institute identity/contact/color and verified, active, normalized domain records.
- Custom User with five roles, pending/active/disabled states and first-password-change flag.
- Normalized, institute-local usernames; separate platform username uniqueness; non-unique contact fields.
- Database constraints for username uniqueness and platform/institute role boundaries.
- Admin, teacher, student and parent profiles with role and same-institute validation.
- Protected foreign keys preserve referenced identity records.
- Authentication backend requires explicit request tenant/platform context; no global username fallback.
- Verified hostname middleware and private/no-store API responses.
- Active tenant and platform permission helpers; temporary-password users denied normal access.
- Audit model with allowlisted-summary intent; event-producing services remain future work.
- Initial migrations for institutes, accounts and audit; generated only, not applied locally.

These are foundation components, not a completed authentication implementation. There are no login or business API routes yet. Services must use scoped querysets and relationship validation; bulk writes bypass model validation and must not accept unvalidated relationships. Database constraints alone do not establish complete tenant isolation.

## Verification

- Frontend Biome: PASS.
- Frontend TypeScript: PASS.
- Frontend production build: PASS.
- Backend Ruff lint and format: PASS (30 Python files).
- Backend non-database tests: 11 PASS; 9 database tests explicitly skipped in the offline run.
- PostgreSQL integration attempt: FAILED during database connection, before tests ran.
- Migration model drift check: no changes detected; live migration-history consistency could not be checked.
- Django system check: no errors; expected auth.W004 warning because username is tenant-unique, not globally unique. The custom backend requires tenant context and deliberately replaces the default global-username backend. Warning remains visible.
- git diff --check: PASS.
- Locked specification integrity: 8/8 unchanged.

Database tests authored cover same username across two institutes, duplicate username constraints, shared contacts, platform role constraints, request-bound login, disabled account/institute session reload, cross-tenant profile rejection, permissions and verified-domain routing. These tests are NOT yet proven passing.

## Exact blocker

PostgreSQL at 127.0.0.1:5432 rejects growthsathi_app_dev with:

    FATAL: password authentication failed for user "growthsathi_app_dev"

Root .env contains a nonempty PGPASSWORD. There is no process PGPASSWORD override. No password value was printed. This is server authentication rejection, not a missing-password or network-resolution error.

Owner must correct the ignored .env password to match the PostgreSQL role, or reset that role password through their authorized PostgreSQL administrator session. Do not send credentials in chat. No database credentials, privileges or authentication configuration were changed. No SQLite fallback was introduced.

## Resume order

1. Verify application-role PostgreSQL access and dedicated test database lifecycle.
2. Run RUN_DATABASE_TESTS=true backend/manage.py test tests --settings=config.settings.test --noinput; fix failures before treating identity foundation as verified.
3. Inspect existing database migration state and apply initial custom-user migrations safely.
4. Complete maintained access/refresh cookie authentication, CSRF, abuse protection, activation/reset/change/logout/revocation and account controls.
5. Academic structure, assignments, enrollment transfer history, parent links and two-institute API isolation proof.
6. Continue all approved modules and portals in owner-specified order, marking pilot readiness only when its acceptance criteria pass, then continue complete V1.

No usable pilot, full V1, production deployment or security acceptance is claimed.

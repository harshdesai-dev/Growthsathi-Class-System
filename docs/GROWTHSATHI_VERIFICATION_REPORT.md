# GrowthSathi Verification Report

Audit date: 2026-09-20

Scope: read-only pre-release verification of the existing repository. No application code, migrations, environment files, dependencies, or commits were changed during this audit. The requested report was the only file created.

## 1. Executive Summary

The repository has a strong locally testable security and workflow baseline. The complete backend suite passes 63 tests; all 4 frontend tests pass; Django checks and migration-drift checks pass; frontend lint, typecheck, and production build pass.

The recent `BatchViewSet` change is correctly implemented by inspection: institute admins, teachers, students, and parents can read only their scoped batches, while non-read methods remain Admin-only. However, one medium application-security finding remains: teacher material reads can include any subject in an assigned batch because of boolean-expression precedence in `materials_for()`.

Findings:

- Critical: 0
- High: 0
- Medium: 2
- Low: 2

Local staging acceptance is **PARTIAL**. Automated evidence is strong, but explicit student/parent batch allow/deny regression tests and teacher same-batch/different-subject material tests are missing. Production readiness is **NOT COMPLETE**: HTTPS/proxy trust, SMTP, persistent private media, backups/restores, real domains, and least-privilege deployment configuration require staging or production verification.

## 2. Automated Test Results

Commands run without modifying files:

| Command | Result |
|---|---|
| `backend/.venv/Scripts/python.exe backend/manage.py test tests --settings=config.settings.test --noinput` | PASS: 63 tests, 0 failures. Django emitted the expected non-unique `User.username` warning. |
| `backend/.venv/Scripts/python.exe backend/manage.py check --settings=config.settings.local` | PASS with the non-unique username warning. |
| `backend/.venv/Scripts/python.exe backend/manage.py makemigrations --check --dry-run --settings=config.settings.local` | PASS: no changes detected. |
| `backend/.venv/Scripts/python.exe -m ruff check backend` | PASS. |
| `backend/.venv/Scripts/python.exe -m ruff format --check backend` | FAIL: existing formatting differences in `backend/config/settings/base.py`, `backend/config/settings/production.py`, and `backend/institutes/middleware.py`. No files were changed. |
| `frontend/npm.cmd test` | PASS: 4 tests, 0 failures. Node emitted a module-type warning for `navigation.ts`. |
| `frontend/npm.cmd run lint` | PASS: 27 files checked. |
| `frontend/npm.cmd run typecheck` | PASS. |
| `frontend/npm.cmd run build` | PASS: optimized Next.js build completed. |

The backend warning about `User.username` being non-unique is consistent with tenant-local usernames and the custom tenant-aware authentication backend. It should remain covered by tenant-bound login tests.

## 3. Role Permission Matrix

| Feature | Super Admin | Admin | Teacher | Student | Parent | Status |
|---|---|---|---|---|---|---|
| Dashboard | Platform metrics | Institute metrics | Scoped metrics | Own metrics | Linked-child metrics | PASS: automated tests and code inspection |
| Students | Not an institute module | Institute management | Assigned-batch read scope | Own record | Linked children only | PASS: automated tests |
| Teachers | Platform administration | Institute management | No management access | No access | No access | PASS: code inspection and tests |
| Parents | Platform administration | Institute management | No management access | No access | Own profile/links via permitted views | PASS: code inspection |
| Batches | Platform context only | Full institute CRUD | Assigned-batch read | Current enrolled batch read | Linked-child current batch read | PARTIAL: implementation verified; explicit student/parent batch pair tests absent |
| Timetable | Platform context only | Institute data | Assigned scope | Enrolled batch | Linked-child scope | PASS/PARTIAL: role code and workflow tests; staging UI still required |
| Attendance | Platform context only | Manage/read institute data | Assigned scope | Own attendance | Linked-child attendance | PASS: automated tests |
| Fees | Platform context only | Manage/read institute data | Denied | Own fees | Linked-child fees | PASS: automated tests |
| Notes & Materials | Platform context only | Institute management | Assigned scope, with subject-read gap | Permitted active scope | No material module in parent navigation; endpoint returns no rows | PARTIAL |
| Exams | Platform context only | Create/publish/manage | Assigned marks scope | Own permitted exam data | Linked-child permitted data | PASS: automated tests |
| Results | Platform context only | Institute results | Permitted results | Own published results | Linked-child published results | PASS: automated tests |
| Announcements | Platform context only | Institute audience management | Permitted audience | Intended audience | Intended linked-child audience | PASS: automated tests |
| Settings | Platform administration | Institute settings | No access | No access | Profile-only routes | PASS: code inspection |
| Platform institute/subscription controls | Full platform scope | No access | No access | No access | No access | PASS: code inspection and platform tests |

## 4. Tenant Isolation Audit

| Requirement | Implementation inspected | Tests found | Result | Risk |
|---|---|---|---|---|
| User login is bound to request tenant | `accounts.backends.TenantBackend`, `accounts.views.LoginView`, tenant middleware | `test_login_is_bound_to_request_tenant`, cookie context tests | AUTOMATED TEST VERIFIED | Low residual risk; deployment proxy trust remains manual |
| JWT cookies cannot cross institute or platform host | `accounts.authentication`, tenant middleware, host-only cookies | `test_cookie_cannot_cross_tenant_or_platform_context` | AUTOMATED TEST VERIFIED | Low |
| Querysets are institute-scoped | `TenantSerializer`, `AdminResourceViewSet`, module-specific `get_queryset()` methods | `test_admin_isolation_and_server_assigned_ownership`, identity database tests | AUTOMATED TEST VERIFIED | Low |
| Object IDs from another institute cannot bypass scope | Scoped querysets and server-side foreign-key validation | cross-tenant identity and link tests | AUTOMATED TEST VERIFIED | Low |
| Parent links stay tenant-bound and active | `students_for()`, `selected_students()`, link serializers | `test_cross_tenant_link_rejected_and_non_admin_transfer_denied`, `test_parent_filter_requires_active_link` | AUTOMATED TEST VERIFIED | Low |
| Forwarded tenant hostname is trusted only with shared secret | `institutes.middleware.TenantContextMiddleware`, Next proxy route | unit/integration auth context coverage; deployment topology not exercised | PARTIALLY VERIFIED | Medium deployment risk if ingress permits spoofed forwarding headers |

## 5. Authentication Audit

- Cookie-based JWT access and refresh tokens are HttpOnly, host-only, and scoped to API paths. **AUTOMATED TEST VERIFIED.**
- CSRF is required for login, refresh, logout, reset, and password mutations. **AUTOMATED TEST VERIFIED.**
- Login is tenant-bound and platform login is separate. **AUTOMATED TEST VERIFIED.**
- Disabled users and inactive institutes are rejected immediately by active-tenant authentication. **AUTOMATED TEST VERIFIED.**
- Temporary-password users are prevented from entering normal modules. **AUTOMATED TEST VERIFIED.**
- Password change revokes active sessions. **AUTOMATED TEST VERIFIED.**
- Activation and reset tokens are single-use, purpose-bound, and tenant-bound. **AUTOMATED TEST VERIFIED.**
- Live SMTP delivery, real activation links, and HTTPS cookie behavior are **MANUAL STAGING TEST REQUIRED**.

## 6. Student Workflow Audit

Student querysets are restricted to the authenticated student and current permitted enrollment data. Student dashboards, attendance, fees, exams, results, announcements, and materials are filtered through server-side scopes. Own-result visibility and unpublished-result denial are covered by content workflow tests.

Student batch read access is implemented through `batches_for()` and current enrollment, but explicit automated assertions for both an allowed batch and an unrelated batch are absent. Classification: **CODE INSPECTION VERIFIED**, not fully automated.

## 7. Teacher Workflow Audit

Teacher scope is based on active `TeacherAssignment` records. Removed assignments immediately remove student, batch, timetable, attendance, exam, and mark-entry access in existing tests. Teachers cannot access fee endpoints. **AUTOMATED TEST VERIFIED.**

Teacher material reads have a scope defect described in Section 16. Assignment subject restrictions apply to uploads and updates, but one branch of material reads permits all subjects for an assigned batch. Classification: **FAIL for subject-level material confidentiality**.

## 8. Parent Workflow Audit

Parent access is based on active `ParentStudentLink` records. Removed links deny student, dashboard, results, announcements, and filtered data access in existing tests. Cross-tenant links are rejected. **AUTOMATED TEST VERIFIED.**

Parent batch access is derived from linked students' current enrollments by `batches_for()`. The implementation is correctly scoped by inspection, but direct allowed/unrelated batch endpoint tests are absent. Classification: **CODE INSPECTION VERIFIED**.

Parent material access is not exposed in the expected parent navigation and `materials_for()` returns no rows for `PARENT`. Whether parent material access is intentionally excluded is not established by an explicit requirement or test. Classification: **NOT VERIFIED** as a product requirement; no unauthorized material access was found by inspection.

## 9. Attendance Audit

Admin and assigned teachers can record attendance. Students see their own attendance, and parents see linked-child attendance. Historical enrollment handling and assignment removal are covered. **AUTOMATED TEST VERIFIED.**

Remaining live browser workflow, responsive behavior, and production-host checks are **MANUAL STAGING TEST REQUIRED**.

## 10. Fees Audit

Admin fee management, payment allocation, reversal, balances, decimal calculations, receipts/reminders, student visibility, parent linked-child visibility, and teacher denial are covered by automated tests. **AUTOMATED TEST VERIFIED.**

Production payment-provider behavior is not present in the inspected local implementation and would require a staging decision/test if external payment integration is required. **NOT VERIFIED** beyond the local fee ledger.

## 11. Notes & Materials Audit

File type validation, private student documents, download authorization, student batch visibility, teacher upload scope, and unrelated-student denial are covered. **PARTIALLY VERIFIED.**

The teacher same-batch/different-subject read case is not tested and is affected by the medium finding in Section 16. Parent material requirements are not explicit in current navigation or tests.

## 12. Exams & Results Audit

The tested workflow covers exam creation, marks access, invalid mark rejection, teacher mark entry, admin publication, unpublished result denial, published student/parent result access, unrelated student denial, and removal of teacher assignment. **AUTOMATED TEST VERIFIED.**

Real browser publication workflow and staging data correctness remain **MANUAL STAGING TEST REQUIRED**.

## 13. Announcements Audit

Audience, publication schedule, expiry, linked-parent scope, and removed-link behavior are covered by automated tests. **AUTOMATED TEST VERIFIED.**

Email/push delivery, if required outside in-app notifications, is **NOT VERIFIED**.

## 14. Batch / Enrollment Audit

`BatchViewSet.initial()` explicitly permits `GET`, `HEAD`, and `OPTIONS` for `ADMIN`, `TEACHER`, `STUDENT`, and `PARENT`. `get_queryset()` calls `batches_for(request.user)`, which applies institute scope and role scope:

- Admin: all institute batches.
- Teacher: active assigned batches.
- Student: batches from current enrollment for that student.
- Parent: batches from current enrollment of actively linked children.

For non-read requests, `require_admin(request.user)` runs before handling the action. This preserves Admin-only create/update/delete behavior. Teacher scope does not widen, and admin behavior is unchanged. Classification: **CODE INSPECTION VERIFIED**.

Student/parent allowed-vs-unrelated batch endpoint assertions should be added in a future test-improvement change, but no code was changed during this audit.

Enrollment transfer closes the old enrollment, creates one current enrollment, preserves history, and updates teacher visibility. **AUTOMATED TEST VERIFIED.**

## 15. Frontend Authorization Audit

`frontend/src/lib/navigation.ts` contains the expected role navigation counts and labels. The portal page checks `canOpen()` after loading the authenticated user and redirects unauthenticated sessions to login. Temporary-password users are routed to password change. Frontend tests verify navigation counts and role restrictions.

This is not the security boundary. Backend permissions and scoped querysets are the authoritative controls and were inspected separately. Direct-route coverage is incomplete for every module/action. Classification: **PARTIALLY VERIFIED**; manual staging direct-URL checks remain required.

The API proxy forwards cookies, CSRF headers, origin/referer, and private tenant headers only when configured with the proxy secret. Deployment ingress must strip or replace client-supplied forwarding headers. Classification: **MANUAL STAGING TEST REQUIRED**.

## 16. Security Findings

### Finding M-01: Teacher material reads are not consistently subject-scoped

- Severity: Medium
- File: `backend/materials/api.py`
- Relevant function: `materials_for()`
- Problem: The teacher scope is built as `Q(batch_id=...) | Q(academic_class_id=...) & Q(subject_id=...)`. Python/Django query-expression precedence makes the batch branch independent of `subject_id`, so a teacher assigned to one subject in a batch may read materials for another subject in that same batch.
- Why it matters: Subject-level teaching assignments are part of the authorization model. A teacher may receive material metadata or private download access outside the assigned subject.
- How it should eventually be fixed: Make the intended grouping explicit so both batch-targeted and class-targeted material predicates include the assigned subject, then add a regression test with two subjects in the same batch. Not fixed during this audit.

### Finding M-02: Forwarded-host trust requires deployment topology enforcement

- Severity: Medium
- Files: `backend/institutes/middleware.py`, `frontend/src/app/api/[...path]/route.ts`, `backend/config/settings/production.py`
- Relevant functions: `TenantContextMiddleware.__call__()`, `proxy()`
- Problem: Tenant resolution can use application-specific forwarded host headers when the shared proxy secret matches. Production also enables forwarded-host processing. Correctness depends on the ingress preventing clients from injecting or preserving untrusted forwarding headers and keeping the proxy secret private.
- Why it matters: A spoofed tenant host combined with a valid session could route requests to the wrong tenant context or cause confusing authentication behavior.
- How it should eventually be fixed: Verify the deployed ingress strips/replaces all client forwarding headers, injects the private headers only in the trusted proxy path, and keep the Django origin private. Add a staging integration test through the real proxy topology. Not fixed during this audit.

### Finding L-01: Ruff format check fails on existing backend files

- Severity: Low
- Files: `backend/config/settings/base.py`, `backend/config/settings/production.py`, `backend/institutes/middleware.py`
- Relevant check: `ruff format --check backend`
- Problem: The configured formatter reports three files as unformatted.
- Why it matters: This can create CI/style drift and reduces confidence that formatting checks are reproducible.
- How it should eventually be fixed: Run the repository-approved formatter in a separate maintenance change and review the diff. Not fixed during this audit.

### Finding L-02: Node reports a module-type warning during frontend tests

- Severity: Low
- File: `frontend/package.json` / `frontend/src/lib/navigation.ts`
- Relevant check: `npm.cmd test`
- Problem: Node reparses `navigation.ts` as an ES module because the package does not declare a module type.
- Why it matters: It adds test noise and may incur avoidable startup overhead; it did not fail the tests.
- How it should eventually be fixed: Align package module metadata and test loading intentionally in a separate tooling change. Not fixed during this audit.

## 17. Test Coverage Gaps

The following important rules are not fully automated by the current suite:

1. Student can retrieve an enrolled/current batch and is denied an unrelated batch through `GET /api/batches/` and detail endpoints.
2. Parent can retrieve a linked child's current batch and is denied an unrelated batch through both list and detail endpoints.
3. Teacher assigned to Subject A in a batch cannot read Subject B material in that same batch.
4. Parent material behavior is not specified by an explicit test or acceptance contract.
5. Every frontend direct URL for every role is not covered by browser automation.
6. Real proxy/forwarded-host behavior through staging ingress is not automated.
7. SMTP delivery, persistent media, backup/restore, and HTTPS behavior are not locally proven.

## 18. Manual Staging Tests Still Required

1. Run the complete role-by-role browser checklist against a deployed staging hostname for both institute tenants and the platform host.
2. Verify student and parent batch list/detail access for linked/current versus unrelated batches.
3. Verify teacher material access for assigned subject versus another subject in the same assigned batch.
4. Verify direct URL navigation to every unauthorized module returns a safe denial or redirect and does not expose data.
5. Verify forwarded-host headers cannot be spoofed through the public ingress and tenant cookies remain host-isolated.
6. Verify HTTPS redirects, Secure cookies, CSRF trusted origins, and logout behavior under the real proxy.
7. Verify activation and reset email delivery using staging SMTP without exposing links or credentials.
8. Verify private media persistence, authorized downloads, backup, and restore.
9. Verify institute deactivation/reactivation through the deployed operator workflow.
10. Verify responsive tablet/mobile layouts and all critical create/edit/publish workflows in a real browser.

## 19. Production Readiness Gaps

### Infrastructure/configuration gaps

- Real production HTTPS, trusted proxy, forwarded-host, and CSRF-origin behavior is not verified.
- SMTP credentials/backend and delivery are not verified.
- `MEDIA_ROOT` is local file storage in the baseline; persistent private storage and restore behavior are not verified.
- PostgreSQL production role, migrations, connection security, backups, and restore drills are not verified.
- Monitoring, alerting, log retention, cleanup jobs, and operational runbooks require deployment validation.
- Real tenant domains, DNS, branding, and certificate configuration are not verified.

### Application-code gaps

- Teacher same-batch/different-subject material reads are insufficiently scoped (Finding M-01).
- Explicit student/parent batch authorization regression tests are missing.
- Frontend direct-route browser coverage is incomplete.

Local staging candidate status: **PARTIAL**.
Production-ready status: **NOT READY / NOT VERIFIED**.

## 20. Final Verification Matrix

| Area | Status | Evidence |
|---|---|---|
| Backend automated regression | PASS | 63 tests passed |
| Frontend automated regression | PASS | 4 tests passed |
| Django system checks | PASS | Warning only for intentional tenant-local username model |
| Migration drift | PASS | No changes detected |
| Frontend lint/typecheck/build | PASS | All completed successfully |
| Python formatting gate | PARTIAL | Ruff check passes; Ruff format check reports 3 existing files |
| Tenant isolation | PASS | Automated auth/identity tests plus scoped queryset inspection |
| Authentication/session/deactivation | PASS | Auth workflow tests |
| Student workflow | PARTIAL | Core scope tested; explicit batch pair tests missing |
| Teacher workflow | PARTIAL | Core assignment/fee rules tested; material subject gap found |
| Parent workflow | PARTIAL | Link and child scope tested; explicit batch pair tests missing |
| Attendance | PASS | Operational workflow tests |
| Fees | PASS | Operational/report tests |
| Notes & Materials | FAIL | Teacher same-batch/different-subject read scope issue |
| Exams & Results | PASS | Publication/private-result workflow tests |
| Announcements | PASS | Audience/schedule/link tests |
| Batch/enrollment | PARTIAL | Implementation verified; direct student/parent batch tests missing |
| Frontend authorization | PARTIAL | Navigation and portal guard tested; direct-route coverage incomplete |
| Proxy tenant routing | MANUAL TEST REQUIRED | Real ingress topology not available locally |
| Email/private media/backups | MANUAL TEST REQUIRED | Deployment-only concerns |
| Staging acceptance | PARTIAL | Local checks pass, identified medium application gap and missing staging evidence |
| Production readiness | NOT VERIFIED | Required infrastructure and deployment evidence absent |

## Final Conclusion

The repository is not ready for an unconditional production-release sign-off. It is a strong local staging candidate for the tested workflows, but the material authorization finding should be addressed before treating the implementation as complete. The remaining deployment and browser checks must be performed in a controlled staging environment. No application changes were made during this audit.

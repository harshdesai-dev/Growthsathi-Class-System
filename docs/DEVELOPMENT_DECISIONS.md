# Approved V1 development decisions

Only explicit approved product-owner decisions override specifications. Casual discussion and implementation assumptions are not overrides.

## Authority

1. Latest explicit product-owner decisions.
2. Final Master Development Specification.
3. Individual Portal Specifications.
4. Login & Access Flow Specification.
5. Whole Project Blueprint.

Stop and report conflicts that this order cannot resolve. The eight locked DOCX specifications remain untouched.

## Active overrides

- Manual student onboarding only. No Excel, CSV, or spreadsheet bulk student import.
- Each institute user requires a username unique within that institute.
- Email/phone are non-unique contact/recovery fields; shared family contacts must not collide. Email login is deferred.
- One active/current batch per student; preserve enrollment/transfer history and the original academic context of historical records.
- PostgreSQL is mandatory for development and integration tests; no SQLite fallback.
- Application correctness depends on resolved institute context, Django/DRF authorization, scoped querysets, centralized policies, server-assigned ownership, same-institute relationship checks, database constraints, and cross-tenant tests.
- PostgreSQL RLS is deferred as additional defense. No RLS/database-role framework in Checkpoint 1.
- Prefer maintained Django/DRF authentication components with minimal custom security code. Final implementation is selected at the authentication checkpoint; no custom token protocol is approved.
- Required later authentication behavior: tenant-bound username/password, short-lived access and refresh credentials, HttpOnly cookies, Secure in production, CSRF, revocation/logout, disabled-account/institute enforcement, activation/reset. No credentials in localStorage/sessionStorage.
- Latest owner authorization: continue through the full V1 in logical tested checkpoints without routine approval pauses. Stop for missing credentials, external permission, destructive operations, unresolved major product decisions, or unsafe continuation.
- Work on develop; preserve foundation, migrations and locked DOCX files. No automatic push or merge to main.

## Scope

One shared codebase: Next.js/TypeScript/App Router/npm, Python/Django 5.2 LTS/DRF, PostgreSQL/Psycopg 3. Five roles: SUPER_ADMIN, ADMIN, TEACHER, STUDENT, PARENT.

Teacher access is limited to assigned batches/subjects, student access to own records and authorized content, parent access to linked children. Institute users cannot access platform controls; teachers cannot access fees.

No standalone CRM, homework, reports, calendar, notifications management, student documents, library, hostel, transport, payroll, inventory, live video teaching, marketplace, advanced accounting/GST, or spreadsheet student import. Reports remain embedded in source modules; student documents remain in Student Profile; holidays/events use Timetable/Announcements.

## Milestone 1 checkpoints

1. Record decisions and establish project/dependency/environment foundations (existing implementation; full V1 continuation now authorized).
2. Institute/domain/custom identity models and audit foundation.
3. Application-level tenant resolution and isolation; RLS remains deferred.
4. Authentication/account lifecycle using maintained components.
5. Minimal academic scope, single active enrollment, parent links, and scope tests.
6. Minimal role routing and scope/account interfaces.
7. Two-institute security proof and acceptance documentation.

Timetable, Attendance business workflows, Fees, Materials/Documents workflows, Exams, Results, Announcements, notification delivery, billing workflows, and PWA push are outside Milestone 1.

## Checkpoint 1 implementation choices

- No domain models, feature pages, login flows, or application migrations.
- Django auth/admin/session apps are intentionally not installed yet: introduce the custom User before account migrations in Checkpoint 2.
- API defaults deny anonymous access; only a minimal process-liveness endpoint is exposed.
- PostgreSQL configuration uses standard PG environment fields; secrets are read from ignored root .env or process environment.
- Local role/database names: growthsathi_app_dev, growthsathi_class_dev, growthsathi_class_test.
- Live database setup is performed interactively by the owner following approved commands; the application must not use postgres.
- UTC storage baseline; institute-specific display settings belong to later domain work.
- Backend .in files define direct dependencies; hash-pinned .txt files lock transitive dependencies.
- Frontend package.json pins direct dependencies and package-lock.json locks the graph.
- No provider-specific hosting, authentication library, or custom tenant machinery is introduced prematurely.

## Milestone 1 final acceptance (future checkpoints)

Two institutes; five roles; correct role routing; activation/reset/logout; account/institute disable; teacher batch/subject scope; student own-record scope; parent link/unlink scope; single current enrollment with preserved history; audited security changes; cross-tenant read/write/relationship/cache denial tests.

Frontend checks use Biome (lint/format) and TypeScript independently. The tested Next.js ESLint dependency chain required unsupported ESLint 9 or failed on ESLint 10; Biome avoids that incompatibility.

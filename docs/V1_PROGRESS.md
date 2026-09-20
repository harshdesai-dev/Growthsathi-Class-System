# V1 implementation progress ? 2026-09-19

Status: IN PROGRESS. Neither PILOT CORE READY nor complete V1 acceptance is declared.

## Implemented

- Preserved the existing develop branch, foundation, dependency locks and locked specifications. No automatic commits, pushes or merges.
- PostgreSQL authentication verified; development migrations applied. Dedicated PostgreSQL test database creation and cleanup work.
- Tenant/domain resolution, institute-local usernames, five roles, profile records, account states, cookie authentication, CSRF, refresh rotation, server-side revocation, activation/reset/password change and login throttling.
- Academic years/classes/subjects/batches, teacher assignments, parent links and student transfers with enrollment history.
- Scoped timetable entries with conflict checks, cancellations and changes; attendance recording, history and summaries; teacher attendance.
- Fee plans/installments, serialized payment recording, allocations, idempotency, reversals and printable receipts. Unused plans can be revised; payment history locks plan replacement. Teacher access is denied.
- Private files/student documents, scoped study materials, official exams, assigned teacher marks, administrator publication and private printable report cards.
- Targeted announcements, in-app event notifications, settings/branding, institute administration, domains, plans/subscriptions and usage limits.
- Shared responsive portal shell with the approved navigation, forms, tables, profile/detail views and parent child selection. PWA manifest, icons and limited offline fallback; private API data is excluded from service-worker caching.
- Two synthetic demo institutes, role accounts, assignments/links, attendance, fees/payment/receipt, exams/results and announcements. Access details remain in an ignored local file.

## Verification

- 51 backend tests PASS using config.settings.test and RUN_DATABASE_TESTS=true against PostgreSQL.
- Coverage includes tenant boundaries, role/assignment/link access, account lifecycle, financial calculations/concurrent payments, academic history, publication and file access.
- Ruff lint and format PASS; migration drift check reports no changes.
- Frontend lint, TypeScript, two automated tests and production build PASS.
- Live Next-to-Django HTTP smoke checks passed for nine institute/platform role contexts. This caught and fixed forwarded-host tenant resolution and API trailing-slash handling.
- One final test invocation accidentally used local settings and failed a Secure-cookie assertion. Re-running the entire suite with the documented test settings passed all 51 tests.
- Django auth.W004 is expected: usernames are unique within a tenant and the custom backend requires tenant context.

## Remaining acceptance work

- Browser is connected. Admin verification has started; remaining role workflows, mobile/responsive and PWA installation checks are incomplete. See the latest checkpoint below. HTTP checks do not substitute for these tests.
- Complete a screen-by-screen comparison against the locked specifications. Weekly/day timetable views are now implemented and partially browser-verified; detailed dashboard/filter/report interactions and full specification reconciliation still need acceptance work.
- Expand frontend behavior tests beyond navigation and service-worker safety, using observed browser workflows.
- Exercise every connected workflow through all relevant role screens, including corrections, empty/error states and historical transfers.
- Configure and verify production HTTPS/reverse-proxy trust, email delivery, media persistence, backups/restores and deployment. Current local operation is not production acceptance.
- Browser push remains deferred; in-app notifications are implemented. Receipts/report cards currently use printable HTML.

The implemented surface and passing tests are substantial progress, not a claim that all specification requirements or security risks have been exhausted.

## Browser reconnection attempt

After the owner reported the Browser ready, the current computer-use inventory still returned empty apps and browsers. An explicit createBrowserTab("iab", "http://localhost:3000") failed with "Browser is not available: iab". No UI verification occurred and no browser acceptance claims were added. Branch remains develop. Full page-level specification reconciliation remains unfinished; the readiness status above is unchanged.

## Connected Browser checkpoint

The in-app Browser is now connected. Local Django and Next services were started. Browser observations confirmed Success Academy at localhost, Bright Classes at 127.0.0.1, and the separate GrowthSathi platform login at platform.localhost. The Success Academy login layout was visually inspected. Next development resource restrictions blocked the alternate institute hostname; next.config.ts now explicitly permits only the three local demo origins. Bright Classes subsequently loaded its branded login form.

Frontend lint (after formatting correction), TypeScript, both automated tests and production build passed. Authenticated browser portal/workflow checks are still pending demo Admin sign-in; no full browser acceptance is claimed. HTTP smoke runs interrupted by configuration-triggered dev-server restarts are not counted as full passes.

With configuration stable, all nine HTTP proxy role contexts passed login, permitted module reads and logout. Browser direct access to Bright Classes /portal/fees while logged out redirected to its branded login page. Environment-secret scan passed. These checks do not replace authenticated browser workflow testing.

## Admin browser verification and fixes

- Observed signed-in Success Academy Admin dashboard, all 13 navigation entries, student list, student profile/enrollment and embedded fee history.
- Compared timetable to Admin specification section 11. Added default Monday-Saturday weekly cards (Sunday appears when it contains lectures), day view, previous/next period, date selection, Today and class/batch/teacher/subject/room filters. Existing authorized lecture edit actions remain available. This is a responsive day-column presentation; a proportional time-slot grid is not yet implemented.
- Added backend date-range filtering and validation after role/tenant scope. Verified removed teacher assignments still deny access. Browser verified two scheduled lectures, filtering to Morning, and an empty day.
- Browser recorded a synthetic INR 100 cash payment, observed paid 6100/pending 3900, verified installment allocation and branded receipt GS-1-00000003. Reversed that synthetic payment with a reason; balance returned to paid 6000/pending 4000. Payment/reversal history remains intentionally preserved.
- Found duplicate refresh calls during simultaneous expired identity checks, confirmed in server logs. Identity checks now share the API client's refresh promise; permission errors after successful refresh retain their own status instead of incorrectly logging the user out. Added two automated regression tests. Browser resumed the Admin exam page without another login.
- Full PostgreSQL suite: 52 PASS. Ruff lint/format PASS; migration drift: none. Frontend lint/typecheck: PASS; 4 tests PASS; production build PASS.
- Exam list rendered published/unpublished states and actions. An attempted incomplete-result publication opened a JavaScript confirmation; subsequent browser controls timed out and supported dialog inspection returned no dialog handle. User dismissal requested. Publication outcome has not been claimed as verified.
- Bright Classes teacher login requested in a separate tab for subsequent role/tenant browser verification. Remaining portal and connected-flow acceptance is unfinished. No PILOT/FULL V1 readiness declaration.

## Publication dialog and attendance correction checkpoint

- Browser recovered after user closed the native publication confirmation. The API had rejected incomplete marks and the result remained unpublished.
- Replaced the exam publication native confirm with an in-app confirmation using the existing Editor, explicit acknowledgement and inline backend validation. Browser verified the incomplete-marks error and normal dialog close behavior.
- Found attendance editor defaulting saved records to Present and using only the current enrollment roster. Added a scoped date-specific roster endpoint that includes saved statuses/remarks and historical enrollment membership. The editor now loads this roster before enabling submission.
- Browser verified the existing Evening-batch Late status preloads correctly. PostgreSQL regression proves historical membership after transfer, Student denial, assigned Teacher access and denial after assignment removal.
- Full PostgreSQL suite: 53 PASS. Ruff lint/format PASS. Frontend lint/typecheck, 4 automated tests and production build PASS. No migration changes required.
- Notes and Materials empty state and upload controls rendered. Full multi-role browser acceptance remains incomplete.

Admin navigation coverage now includes all 13 modules at page-load level, not full workflow acceptance. Teacher/Parent/Batch lists, Announcements, Settings and Results rendered; result rows show 42/50 = 84 percent Pass. Corrected Add batch/lecture labels. Bright Classes teacher login tab prepared and awaiting sign-in. Secret scan passed and eight locked specifications remain unchanged.

# Manual acceptance checklist

Use this checklist after the local automated suite is green and before any pilot or sales demo. This file intentionally avoids demo credentials and only records browser-based verification steps.

## 1. Login and tenant context
- [ ] Success Academy login works with institute-branded UI
- [ ] Bright Classes login works with institute-branded UI
- [ ] platform login works separately from institute login
- [ ] invalid host or cross-tenant access redirects to correct login flow
- [ ] disabled account rejects access immediately
- [ ] inactive institute rejects access immediately
- [ ] logout clears cookies and ends session

## 2. Admin
- [ ] Dashboard shows expected totals and sections
- [ ] Students module loads, creates and edits valid records
- [ ] Teachers module loads and respects assignment data
- [ ] Parents module loads and respects linked-student data
- [ ] Batches module loads and creation/edit flows work
- [ ] Timetable loads weekly/day views and filters correctly
- [ ] Attendance page loads roster and correct status summary
- [ ] Fees module shows balance and payment history
- [ ] Materials page shows upload and visibility rules
- [ ] Exams list loads and publication flow is correct
- [ ] Results page shows published results with correct role filtering
- [ ] Announcements send to the correct audience
- [ ] Settings save branding and institute preferences

## 3. Teacher
- [ ] Dashboard loads, with no fee data exposed
- [ ] My Batches matches assigned batches
- [ ] Timetable loads scheduled lectures for scope
- [ ] Attendance recording works only for assigned batch/subject
- [ ] Materials upload works for assigned scope only
- [ ] Exams and result marks entry is scoped and restricted correctly
- [ ] Announcements show expected audience content
- [ ] Profile loads and edits correctly

## 4. Student
- [ ] Dashboard loads with private, current-batch data only
- [ ] Timetable shows only enrolled batch data
- [ ] Attendance shows own attendance and correct history
- [ ] Fees shows own fee account only
- [ ] Materials are visible for assigned batches/classes
- [ ] Exam results show only own published results
- [ ] Announcements show intended messages only
- [ ] Profile loads

## 5. Parent
- [ ] Dashboard shows linked-child summary only
- [ ] Attendance shows linked child records only
- [ ] Fees shows linked child fee records only
- [ ] Exams and results show linked child published results only
- [ ] Announcements target linked child context only
- [ ] Child Profile and My Profile behave correctly

## 6. Super Admin
- [ ] Dashboard loads platform metrics
- [ ] Institutes list and manage activation status correctly
- [ ] Create Institute flow creates institute and initial admin account
- [ ] Subscriptions view and adjustments is correct
- [ ] Domains / Branding loads valid domain and branding states
- [ ] Usage & Support shows correct metrics and support data

## 7. Workflow checks
- [ ] Admin creates exam, teacher marks, admin publishes, student sees result, parent sees linked result
- [ ] Teacher/Admin records attendance, summaries update, student and parent see own data
- [ ] Fee payment records, balances update, receipts render, student/parent see changes, teacher remains denied
- [ ] Material uploads flow to the right batch/class and unrelated users cannot access it
- [ ] Batch transfer closes old enrollment, creates new active enrollment, preserves history
- [ ] Announcements respect sender authority and recipient audience
- [ ] Institute deactivation blocks access and reactivation restores it

## 8. Production readiness checks
- [ ] HTTPS and trusted proxy configuration is correct in deployment environment
- [ ] Postgres connection and migrations succeed in production settings
- [ ] secure cookies and CSRF are active under HTTPS
- [ ] private media storage is persistently configured and authorized
- [ ] email delivery is configured for activation/reset without exposing secrets
- [ ] backup/restore process has been practiced and verified
- [ ] supported hostnames and branding are configured for the real deployment domain

## 9. Final sign-off
- [ ] All automated checks pass locally
- [ ] Manual browser checklist is fully complete
- [ ] No secrets or credentials are exposed in repo or docs
- [ ] Pilot/demo is approved for the target institute(s)

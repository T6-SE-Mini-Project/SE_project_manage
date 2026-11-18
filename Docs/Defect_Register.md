# Defect Register — Online Book Store

**Project:** Online Book Store
**Team:** T6
**Last updated:** 18 November 2026

| ID | Description | Severity | Status | Evidence |
|---|---|---|---|---|
| DEF-01 | Missing static-files manifest caused the Django admin authorization test to error during the initial test run. | Low | **Resolved** — test environment only; production configuration was not changed. | The manifest was generated with `collectstatic`; the isolated test and the full suite passed. Current suite: 342 backend tests. |
| DEF-02 | Backup endpoint reported `fresh=False` and `runs=0` in the earlier integration smoke evidence. | High | **Resolved** — later backup execution and verification succeeded. | `Docs/evidence/tc-obs-024-backup-evidence.txt`: 13 records written, `verify_backups` reported `fresh=true` at 0.00 h, and `GET /api/admin/backups/` returned the execution record. |
| DEF-03 | The 99% monthly availability target has not been established through continuous monitoring. | Medium | **Open** — requires a monitoring period. | `Docs/Validation_Evidence.md` (TC-OBS-020); Test Plan v1.1 marks OBS-NF-002 **Not Verified**. |
| DEF-04 | The SQLite concurrent-write load test produced HTTP 500 errors because of database locking. | Medium | **Open** — MySQL write-path retest pending. | `Docs/evidence/tc-obs-023-load-test-writes.txt`; Test Plan v1.1 marks OBS-NF-005 **Not Verified**. |
| DEF-05 | Authenticated customer sessions did not have an application-level inactivity timeout. Firebase persistence and token refresh allowed sessions to remain active; the Django 900-second cookie applies to guest cart/order data. | High | **Resolved** — implementation added in commit `8a92a67`. | `frontend/src/hooks/useAuth.tsx` enforces a 15-minute inactivity logout; 8 `useAuth` tests pass; Test Plan v1.1 marks OBS-SR-006 **Pass**. |

## Regression test summary — 18 November 2026

- **Backend:** 342 tests passed, 0 failures, 0 errors
  (`python manage.py test --settings=config.settings_test`).
- **Frontend:** 27 tests passed across 6 test files (`npm test`).
- **Frontend type-check:** passed (`npm run typecheck`).
- **Frontend production build:** passed (`npm run build`).
- **CI:** `.github/workflows/main.yml` runs the backend suite against MySQL 8.0
  and the frontend type-check, tests and build.
- **Production checks:** frontend and API returned HTTPS 200; `/healthz/`
  returned `{"status": "ok"}`.

## Notes

- DEF-01 was a test-environment configuration issue; no production change was
  required.
- DEF-02 was closed after a later successful backup run; the earlier
  `fresh=False` observation is retained in the historical evidence.
- DEF-03 requires continuous availability monitoring over a full month. A
  single health check is not sufficient.
- DEF-04 requires re-running the write-path load test against MySQL. The
  SQLite failure is an artefact of SQLite's single-writer locking, but the
  requirement is not marked as passed until the MySQL run is recorded.
- DEF-05 is closed with the inactivity logout and its unit tests; no browser
  E2E test exists, so the evidence is component-level plus manual browser
  verification.
- OBS-SR-003 password-storage validation is covered separately by Issue #15
  and the Firebase update in `Docs/Validation_Evidence.md`.
- Open verification gaps are tracked in `Docs/Test_Plan_2.docx` and
  `Docs/Validation_Evidence.md`.

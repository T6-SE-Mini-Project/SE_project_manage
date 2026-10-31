# Defect Register — Online Book Store

| ID | Description | Severity | Status | Evidence |
|---|---|---|---|---|
| DEF-01 | Missing static-files manifest caused the Django admin authorization test to error during the initial test run. | Low | Resolved in test environment | collectstatic completed; isolated test and full 330-test suite passed. |
| DEF-02 | Backup endpoint reported fresh=False and runs=0 in existing integration evidence. | High | Open — investigation required | Docs/evidence/integration-smoke-test.txt |
| DEF-03 | Monthly availability target of 99% has not been established through continuous monitoring. | Medium | Not verified | Docs/Validation_Evidence.md |
| DEF-04 | SQLite concurrent-write load test produced HTTP 500 errors due to database locking. | Medium | MySQL verification pending | Docs/evidence/tc-obs-023-load-test-writes.txt |

## Regression Test Summary

- Django backend: 330 tests passed, 0 failures, 0 errors.
- Frontend automated tests: GitHub Actions verification pending.
- Existing integration evidence: Docs/evidence/integration-smoke-test.txt.
- Production MySQL concurrent-write behaviour: not verified.

## Notes

- DEF-01 required a test-environment static-files manifest; no application-code fix was needed.
- DEF-02 requires investigation of backup execution and scheduling.
- DEF-03 requires continuous monitoring over the measurement period.
- DEF-04 requires retesting against MySQL.
- Unexecuted frontend tests are not marked as passed.

# \# Defect Register — Online Book Store
# | ID | Description | Severity | Status | Evidence |

# |---|---|---|---|---|

# | DEF-01 | Missing static-files manifest caused the Django admin authorization test to error during the initial test run. | Low | Resolved in test environment | Isolated test and full 331-test suite passed. |

# | DEF-02 | Backup endpoint reported fresh=False and runs=0 in existing integration evidence. | High | Open - investigation required | Docs/evidence/integration-smoke-test.txt |

# | DEF-03 | Monthly availability target of 99% has not been established through continuous monitoring. | Medium | Not verified | Docs/Validation\_Evidence.md |

# | DEF-04 | SQLite concurrent-write load test produced HTTP 500 errors due to database locking. | Medium | MySQL verification pending | Docs/evidence/tc-obs-023-load-test-writes.txt |

# | DEF-05 | Authenticated customer sessions do not have an application-level inactivity timeout. Firebase browser persistence and token refresh allow sessions to remain active; the Django 900-second session timeout applies to guest session data, not authenticated Firebase inactivity. | High | Open - implementation required | Frontend inactivity search; frontend/src/firebase.ts; backend/config/settings.py |
# \## Regression Test Summary
# \- Django backend: 331 tests passed, 0 failures, 0 errors.

# \- Frontend TypeScript typecheck: passed.

# \- Frontend automated tests: 17 tests passed across 5 test files.

# \- Frontend production build: passed.

# \- Existing integration evidence: Docs/evidence/integration-smoke-test.txt.

# \- Production MySQL concurrent-write behaviour: not verified.
# \## Notes
# \- DEF-01 required a test-environment static-files configuration; production configuration was not changed.

# \- DEF-02 requires investigation of backup execution and scheduling.

# \- DEF-03 requires continuous monitoring over the measurement period.

# \- DEF-04 requires retesting against MySQL.

# \- DEF-05 requires implementation and validation of an inactivity-based logout for authenticated Firebase sessions.

# \- OBS-SR-003 password storage validation is covered separately by Issue #15.

# \- Frontend and backend HTTPS checks passed against the deployed endpoints.

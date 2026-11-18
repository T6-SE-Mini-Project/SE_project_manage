# As-Built Deviations and Design Decisions

**Project:** Online Book Store
**Team:** T6
**Recorded:** 18 November 2026
**Scope:** Differences between the original SRS/plan wording and the delivered system.

This record exists so the evaluator can see where the implementation deliberately differs from
the original documents. The SAD has been updated to describe the as-built architecture.

| ID | Original / planned | As built | Reason | Requirement impact |
|---|---|---|---|---|
| DEV-01 | SAD described a MERN stack (React, Express, MongoDB). | React 18 + TypeScript, Django 5, MySQL 8.0. | Django and MySQL were selected at project start for the team's Python/database experience and the managed MySQL deployment. | No requirement is removed. The SAD, component diagram and API table now describe the Django implementation. |
| DEV-02 | Django registration/login pages with app-managed password hashing. | Firebase Authentication handles email/password and Google sign-in. Django verifies Firebase ID tokens and creates/links the local user. | Removes app-managed credential storage and adds Google sign-in. | OBS-NF-003 and OBS-SR-003 are satisfied by delegation: Firebase owns the credential; Django stores an unusable password. |
| DEV-03 | Checkout collected only order/cart details. | Checkout also captures and stores a billing address. | Needed for a realistic card checkout and the order record. | Extends OBS-F-010; no SRS requirement is contradicted. |
| DEV-04 | No cache or rate-limiting component in the SRS. | Redis (Upstash) response cache and per-caller rate limits; HTTP 429 with `Retry-After`. | Supports OBS-NF-001 and protects sign-in, payment and review endpoints. | Additional control; supports the performance and security objectives. |
| DEV-05 | Session timeout value left to implementation. | 15-minute inactivity logout in `frontend/src/hooks/useAuth.tsx`; Django guest session cookie remains for guest cart/order data. | Gives OBS-SR-006 a concrete, testable value. | OBS-SR-006 passes; covered by 8 `useAuth` tests. |
| DEV-06 | Supported payment mechanism. | Deterministic mock card gateway with success, decline and insufficient-funds test cards. | No live payment provider was available for the mini-project. | OBS-F-012/F-013 are demonstrated end to end against the mock; real card-network settlement is out of scope. |
| DEV-07 | Deployment mechanism not specified. | React on Vercel, Django/Gunicorn on Render, MySQL on Aiven, Redis on Upstash. | Free/managed hosting suitable for the project. | OBS-SR-004 passes on the deployed HTTPS endpoints. |
| DEV-08 | Administrator "manage customers". | Administrator can activate/deactivate customer accounts and view customer order summaries. | Makes the requirement concrete without deleting customer history. | Extends OBS-F-018. |
| DEV-09 | Browser end-to-end automation not specified. | Automated unit/integration tests plus an HTTP API smoke test; browser checks recorded manually. | Time and scope of the mini-project. | No automated Playwright/Cypress suite; NF-002/NF-005 evidence remains limited as recorded in the Test Plan. |

## Verification limitations

- OBS-NF-002 (99% monthly availability) is **not verified**: only point-in-time health checks exist.
- OBS-NF-005 (500 concurrent users) is **not verified on MySQL**: the read path passed on SQLite,
  but the write path failed under SQLite locking. A MySQL load retest is still required.
- OBS-NF-001, OBS-NF-004 and OBS-NF-006 are **partially verified**; see Test Plan v1.1.
- Customer registration/login and the authenticated cart flow do not have an automated browser
  end-to-end test; they are covered by API/unit tests and manual browser checks.

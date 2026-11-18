# Retrospective Pull-Request Review

**Project:** Online Book Store
**Team:** T6
**Review date:** 18 November 2026
**Scope:** All 17 pull requests in the repository (PR #22 and PR #29–#44).

## Why this record exists

The GitHub history shows that most pull requests were merged without a recorded
approval. Only PR #41 has a formal human approval; two pull requests received
Copilot review comments, and the rest have no formal review record. That history
cannot be changed retroactively, and this document does not claim that a review
took place at merge time.

Instead, the team reviewed the merged changes on **18 November 2026** as part of
final-submission preparation. This record states what was checked, what was
accepted, and what remains a process weakness. The review comments added to the
pull requests are dated 18 November 2026 by GitHub and are labelled as
retrospective.

## Method

1. Read each pull request's title, description, changed-file list and merge
   commit.
2. Spot-checked the delivered code and documentation against the linked issue
   and the SRS requirement.
3. Re-ran the current automated suites from `main`:
   - backend: **342 tests passed** (`python manage.py test --settings=config.settings_test`);
   - frontend: **27 tests passed across 6 files** (`npm test`);
   - frontend type-check and production build: **passed**.
4. Cross-checked the result against `Docs/Test_Plan_2.docx` v1.1 and
   `Docs/Validation_Evidence.md`.

## Pull-request outcomes

| PR | Delivered | Author | Formal review at merge | Retrospective outcome |
|---|---|---|---|---|
| #22 | Revised Test Plan with 1:1 traceability | PuneethV333 | None | **Accepted; superseded by Test Plan v1.1** (results now recorded) |
| #29 | Customer registration | SN123-123 | None | **Accepted** — covered by accounts tests and Firebase sign-up flow |
| #30 | Customer login | SN123-123 | None | **Accepted** — covered by accounts/session tests |
| #31 | Django tests in GitHub Actions | SN123-123 | None | **Accepted** — CI runs backend tests against MySQL 8.0 |
| #32 | Book browsing and shopping cart | hadagaliprabhu14-ship-it | None | **Accepted** — catalogue, search, cart and totals tests pass |
| #33 | Account security controls | sudevsuresh | None (merged by another member) | **Accepted** — middleware and protected-access tests pass |
| #34 | Password-storage validation | sudevsuresh | None | **Accepted** — Firebase delegation and unusable Django password verified |
| #35 | Orders, payments, reviews and administrator APIs | PuneethV333 | None | **Accepted** — the largest PR; spot-checked structure and all related suites pass |
| #36 | Production configuration for Render, Vercel and Aiven MySQL | PuneethV333 | None | **Accepted** — deployment files reviewed; live endpoints respond |
| #37 | Render hostname and DEBUG fail-safe | PuneethV333 | None | **Accepted** — production health check passes |
| #38 | Vercel `/api` rewrite | PuneethV333 | None | **Accepted** — frontend proxy path verified |
| #39 | Deployed URLs in README | PuneethV333 | Copilot comment only | **Accepted** — documentation-only change |
| #40 | Firebase authentication, Redis cache and rate limiting | PuneethV333 | Copilot comment only | **Accepted** — auth/cache/rate-limit tests pass |
| #41 | Final security validation | sudevsuresh | **Approved by PuneethV333** | **Accepted** — the only PR with a formal human approval |
| #42 | Billing-address branch (closed) | PuneethV333 | Copilot comment only | **Superseded** by #43 and #44; no merge |
| #43 | Billing-address backend and order changes | hadagaliprabhu14-ship-it | None | **Accepted** — checkout/order tests pass |
| #44 | Billing-address checkout UI | hadagaliprabhu14-ship-it | None | **Accepted** — checkout UI and validation tests pass |

## Findings and follow-ups

- **Review discipline was the main process weakness.** Self-merging was common,
  and several PRs had no owner approval. For future work, require at least one
  approval from a team member who did not author the change, and do not merge
  on the author's approval alone.
- **PR size:** #35 combined several issues and was very large. Smaller PRs would
  make review and defect isolation easier.
- **Evidence linkage:** most PRs describe the change but do not link the
  executed test result. Future PRs should link the test case and evidence file
  in the description.
- **No code changes were required by this retrospective review.** The current
  suites pass; the remaining gaps are verification gaps (OBS-NF-002 and
  OBS-NF-005) and the missing Sprint 2 video link, which are tracked in the
  Test Plan, Defect Register and Agile Record.

## Current status

| Check | Result |
|---|---|
| Backend test suite | 342 passed |
| Frontend test suite | 27 passed across 6 files |
| Frontend type-check | Passed |
| Frontend production build | Passed |
| Formal approval coverage | 1 of 17 PRs at merge time; retrospective review recorded for all |
| Open defects | DEF-03 (availability monitoring), DEF-04 (MySQL write-path load test) |

This document is evidence of an honest retrospective review, not evidence of
reviews that did not happen.

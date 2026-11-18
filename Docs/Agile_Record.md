# Agile Delivery Record

**Project:** Online Book Store
**Team:** T6
**Recorded:** 18 November 2026

This is a retrospective record. The team tracked work through GitHub issues and pull requests;
a project-board export was not retained. The sprint allocation below was reconstructed from the
issue creation/closure dates and the pull-request merge dates. **Story points are retrospective
estimates recorded on 18 November 2026, not contemporaneous sprint-planning estimates.** They are
included so the backlog can be assessed consistently.

## Team

| Member | Role | Main delivery area |
|---|---|---|
| Puneeth V (PES1UG24CS686) | Backend / integration lead | Orders, payments, reviews, administrator APIs, deployment, documentation |
| Prabhu Hadagali (PES1UG24CS682) | Frontend / design lead | SAD, catalogue, cart, billing checkout |
| Sudev Suresh (PES1UG24CS694) | Security / validation lead | Authentication controls, password-storage validation, final security validation |
| SN123-123 | Customer account / testing | Registration, login, CI, integration and regression testing |

## Sprint allocation

| Sprint | Dates | Goal | Issues | Points |
|---|---|---|---|---:|
| Sprint 1 | 28 Sep – 26 Oct 2026 | Deliver the core customer and administrator workflows and first validation evidence | #1–#18, #24 | 76 |
| Sprint 2 | 27 Oct – 3 Nov 2026 | Production deployment, Firebase authentication, caching/rate limiting, billing, final security and regression evidence | #19–#21, #23, #25–#28 | 24 |
| **Total** | | | **27 issues** | **100** |

## Backlog and story points

| Issue | Title | Assignee | Sprint | Estimate |
|---|---|---|---:|---:|
| #1 | Implement customer registration | SN123-123 | 1 | 3 |
| #2 | Implement customer login | SN123-123 | 1 | 3 |
| #3 | Implement authentication and security controls | sudevsuresh | 1 | 5 |
| #4 | Implement book browsing and book details | hadagaliprabhu14-ship-it | 1 | 3 |
| #5 | Implement book search and filtering | hadagaliprabhu14-ship-it | 1 | 5 |
| #6 | Implement shopping cart management | hadagaliprabhu14-ship-it | 1 | 5 |
| #7 | Calculate shopping cart total | hadagaliprabhu14-ship-it | 1 | 2 |
| #8 | Implement order placement and availability checking | PuneethV333 | 1 | 5 |
| #9 | Implement payment processing and order confirmation | PuneethV333 | 1 | 8 |
| #10 | Implement order history and cancellation | PuneethV333 | 1 | 5 |
| #11 | Implement book reviews | PuneethV333 | 1 | 5 |
| #12 | Implement administrator catalogue and order management | PuneethV333 | 1 | 8 |
| #13 | Validate search response-time requirement | hadagaliprabhu14-ship-it | 1 | 2 |
| #14 | Validate system availability requirement | SN123-123 | 1 | 2 |
| #15 | Validate secure password storage | sudevsuresh | 1 | 2 |
| #16 | Validate shopping cart usability requirement | hadagaliprabhu14-ship-it | 1 | 2 |
| #17 | Validate scalability under 500 concurrent users | PuneethV333 | 1 | 3 |
| #18 | Validate automated order and inventory backups | PuneethV333 | 1 | 3 |
| #19 | Validate Online Book Store security objectives | sudevsuresh | 2 | 3 |
| #20 | Validate security requirements | sudevsuresh | 2 | 3 |
| #21 | Validate remaining security requirements | sudevsuresh | 2 | 3 |
| #23 | Validate remaining security requirements | sudevsuresh | 2 | 3 |
| #24 | Implement administrator customer management and sales reports | PuneethV333 | 1 | 5 |
| #25 | Execute integration and system testing | SN123-123 | 2 | 3 |
| #26 | Execute regression testing and maintain defect records | SN123-123 | 2 | 3 |
| #27 | Execute integration and system testing | SN123-123 | 2 | 3 |
| #28 | Execute regression testing and maintain defect records | SN123-123 | 2 | 3 |

Issue #22 does not exist; pull request #22 delivered the revised Test Plan.

## Pull requests

| PR | Delivered | Author | Merged |
|---|---|---|---:|
| #29 | Customer registration | SN123-123 | 2026-10-25 |
| #30 | Customer login | SN123-123 | 2026-10-25 |
| #31 | Django tests in GitHub Actions | SN123-123 | 2026-10-25 |
| #32 | Book browsing and shopping cart | hadagaliprabhu14-ship-it | 2026-10-25 |
| #33 | Account security controls | sudevsuresh | 2026-10-26 |
| #34 | Password-storage validation | sudevsuresh | 2026-10-26 |
| #35 | Orders, payments, reviews and administrator APIs | PuneethV333 | 2026-10-26 |
| #36 | Production deployment configuration | PuneethV333 | 2026-10-28 |
| #37 | Render hostname and DEBUG fail-safe | PuneethV333 | 2026-10-28 |
| #38 | Vercel API rewrite | PuneethV333 | 2026-10-28 |
| #39 | Deployed URLs in README | PuneethV333 | 2026-10-29 |
| #40 | Firebase auth, Redis cache and rate limiting | PuneethV333 | 2026-10-30 |
| #41 | Final security validation | sudevsuresh | 2026-11-01 |
| #42 | Superseded billing-address branch | PuneethV333 | closed |
| #43 | Billing-address backend and order changes | hadagaliprabhu14-ship-it | 2026-11-02 |
| #44 | Billing-address checkout UI | hadagaliprabhu14-ship-it | 2026-11-03 |

## Demo videos

- Sprint 1: <https://drive.google.com/file/d/1qrwcIV2dMNZxmOVItZbek1h4R9Q5fcbh/view?usp=sharing>
- Sprint 2: recording ready; link to be added in `Docs/Demo_Video.md` before submission.

## Retrospective review

All 17 pull requests were reviewed after merge on **18 November 2026**.
Retrospective comments were posted on each PR, and the outcomes are recorded in
`Docs/Retrospective_Review.md`. GitHub dates those comments 18 November 2026;
they are not backdated and do not claim an approval that was not recorded at
merge time.

## Known process gaps

- Story points were not recorded during the sprints; the estimates above are retrospective.
- A GitHub Project board was not retained in a form that can be exported to the repository.
- Most PRs were merged without a recorded owner approval. The gap is documented in
  `Docs/Retrospective_Review.md`; it cannot be corrected retroactively.
- The Sprint 2 demo video link is still pending.

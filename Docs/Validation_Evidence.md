# Validation Evidence — Issues #4, #5, #6, #7, #13, #16

- **Branch:** `feature/book-browsing-details`
- **Execution date:** 2026-10-25
- **Local environment:** Windows, Python 3.13.7, Django 5.2.18, Node.js 22.19.0, npm 10.9.3, React 18.3.1, Vite 5.4.21, Vitest 2.1.9
- **Local test database:** Isolated in-memory SQLite via `config.settings_test`. No development MySQL credentials were used, and no migrations were applied to the development database.
- **CI database:** MySQL 8.0 (`.github/workflows/main.yml`). MySQL execution was pending CI/push when this evidence was recorded.

## Test-case mapping and results

| Test case | Requirement | Implementation | Automated evidence | Result |
|---|---|---|---|---|
| TC-OBS-003 | OBS-F-003 Browse books | `GET /api/books/`; catalogue page at `/books` | `books.tests.BookApiTests.test_catalogue_returns_all_books_in_model_order`, `test_catalogue_returns_summary_fields` | Pass |
| TC-OBS-004 | OBS-F-004 Book search | Search across title, author, ISBN and description; catalogue search form | `BookSearchFilterTests.test_search_by_title`, `test_search_by_author`, `test_search_by_isbn`, `test_search_by_description_keyword` | Pass |
| TC-OBS-005 | OBS-F-005 Filter books | Category, author, minimum/maximum price and availability filters, individually and combined | `BookSearchFilterTests.test_filter_by_category`, `test_filter_by_author`, `test_filter_by_price_range`, `test_filter_by_availability`, `test_filters_combine` | Pass |
| TC-OBS-006 | OBS-F-006 Book details | `GET /api/books/<id>/`; details page at `/books/<id>` | `BookApiTests.test_details_return_book_information`, `test_unknown_book_returns_json_404` | Pass |
| TC-OBS-007 | OBS-F-007 Add book to cart | `POST /api/cart/items/`; Add to cart action on the details page | `CartApiTests.test_add_book_to_cart`, `test_add_same_book_increments_quantity`, `test_out_of_stock_book_is_rejected` | Pass |
| TC-OBS-008 | OBS-F-008 Manage cart items | `PATCH` and `DELETE /api/cart/items/<id>/`; cart quantity and remove controls | `CartApiTests.test_update_cart_item_quantity`, `test_remove_cart_item`, `test_cart_is_scoped_to_the_session` | Pass |
| TC-OBS-009 | OBS-F-009 Calculate cart total | Server-side subtotal and total calculation, displayed on the cart page | `CartApiTests.test_total_reflects_prices_and_quantities`, `test_total_updates_when_contents_change` | Pass |
| TC-OBS-019 | OBS-NF-001 Search response time | Catalogue search endpoint | `books.tests.SearchPerformanceTests.test_search_response_time_target` | **Partially verified.** Twenty sequential Django test-client requests over 40 SQLite rows passed the configured 3.0-second assertion: minimum 0.0008 s, p90 0.0023 s, maximum 0.0027 s; 20/20 were within 3.0 s. This does not prove the SRS normal-operating-condition target or the related OBS-NF-005/AT-005 requirement for 500 concurrent users. HTTP/WSGI, concurrent load and MySQL performance remain unverified. |
| TC-OBS-022 | OBS-NF-004 Cart usability | Details-page primary action | `frontend/src/components/AddToCartButton.test.jsx`; guest browser flow; `cart.tests.CartApiTests.test_authenticated_cart_is_linked_to_user` | **Partially verified.** The guest browser flow adds a book through one primary interaction, and the API test verifies authenticated-cart association. The registered-customer browser flow has not been verified end to end because the React app has no login UI and does not integrate directly with the Django login page. Complete authenticated-customer browser usability is not claimed. |

## Commands and actual results

The following commands and outputs were recorded for the book-browsing and cart work.

```powershell
# Run from the repository root
.\.venv\Scripts\python.exe manage.py check --settings=config.settings_test
# System check identified no issues (0 silenced).

.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --settings=config.settings_test
# No changes detected

.\.venv\Scripts\python.exe manage.py test accounts books cart --settings=config.settings_test -v 2
# Ran 52 tests in 0.403s
# OK
# TC-OBS-019 search timings (seconds): min=0.0008 p90=0.0023 max=0.0027; 20/20 within 3.0s
```

From the `frontend/` directory:

```cmd
npm test
```

Recorded result: 1 test file passed, 1 test passed.

```cmd
npm run build
```

Recorded result: 44 modules transformed; build completed in 881 ms.

## Browser and HTTP verification

The following browser and HTTP checks were recorded using a temporary SQLite-backed server, not the development database.

- The catalogue loaded seven seeded books. Search with `q=clean` returned one book, and the category/availability/price filter returned the expected two books.
- The details endpoint returned the stored title, author, ISBN, publisher, publication date, price, stock and description. An unknown book returned an HTTP 404 JSON response.
- The Vite proxy at `http://127.0.0.1:5173/api/books/` returned the same catalogue, confirming frontend/backend integration.
- In the guest browser flow at `http://127.0.0.1:5173/books`, the user navigated from the catalogue to Clean Code details and clicked **Add to cart** once. The page displayed “Added to cart.” and a **View cart** link.
- The cart displayed quantity 1, line total `$42.50` and order total `$42.50`.
- Increasing the quantity to 2 updated the line total and order total to `$85.00`. Removing the item displayed the empty-cart state.
- For the CSRF/session flow, `GET /api/csrf/` issued a token, and add, update, fetch and remove cart actions succeeded through the proxied session.

## Caveats for Issues #4, #5, #6, #7, #13 and #16

- Local backend tests and the recorded performance measurement use SQLite because MySQL credentials were not available and the development database was not to be migrated. The suite is configured to run against MySQL 8.0 in CI.
- **TC-OBS-019 scope:** The performance test made 20 sequential requests through Django's test client against 40 in-memory SQLite rows. The minimum was 0.0008 s, p90 was 0.0023 s, and maximum was 0.0027 s; 20/20 requests completed within the configured 3.0-second limit. This does not exercise HTTP/WSGI, concurrent load or MySQL. It is not a 500-concurrent-user normal-load test. The SRS OBS-NF-001 normal-operating-condition target and related OBS-NF-005/AT-005 scalability requirement remain unverified.
- **TC-OBS-022 scope:** Browser verification was performed as a guest. `CartApiTests.test_authenticated_cart_is_linked_to_user` verifies API-level cart association when an authenticated Django session is present, but it is not an end-to-end browser test. At the time of this execution the React app had no login UI, so the registered-customer flow required by TC-OBS-022 was not verified end to end. (It has a Firebase login UI as of 2026-10-29, and the Django login page it refers to has been removed; the registered-customer browser flow has not been re-run, so no end-to-end verification is claimed here either.)
- The cart is session-based and also associates with the authenticated user when a Django session is present. `CartApiTests.test_authenticated_cart_is_linked_to_user` covers registered-customer association.
- Prices are displayed in USD via `Intl.NumberFormat`. This is an assumption because the SRS does not specify a currency.

---

# Validation Evidence — Issue #15: Password Storage

- **Branch:** `feature/issue-15-password-storage-validation`
- **Execution date:** 2026-10-26
- **Requirements:** OBS-NF-003 and OBS-SR-003
- **Scope:** Validate password storage during customer registration.

## Test-case mapping and results

| Test case | Requirement | Validation | Automated evidence | Result |
|---|---|---|---|---|
| TC-OBS-021 | OBS-NF-003 | Verify that the stored credential differs from the original plaintext password and uses an encoded password hash. | `accounts.tests.PasswordStorageTests.test_password_is_hashed` | Pass |
| TC-OBS-030 | OBS-SR-003 | Verify that Django can validate the original password against the stored hash and that the stored value uses the configured password-hashing format. | `accounts.tests.PasswordStorageTests.test_password_is_hashed`, `accounts.tests.PasswordStorageTests.test_password_hash_uses_configured_hasher` | Pass |

## Update — 2026-10-29: credentials moved to Firebase

Customer sign-in moved to Firebase Authentication (email/password and
Google), and the Django template registration and login pages were
removed with it. The requirements are unchanged and still hold, but what
they apply to has changed:

- **Customer credentials are no longer stored by this project at all.**
  Firebase holds them; a customer's Django account is created with an
  *unusable* password, so there is no credential to hash or to leak.
  `accounts.tests.PasswordStorageTests.test_a_firebase_account_stores_no_password`
  asserts that, and
  `accounts.tests.PasswordStorageTests.test_no_password_endpoint_remains`
  asserts that no password endpoint survived — a second credential path
  would bypass Firebase.
- **The passwords that remain** are the administrator accounts for
  Django's own admin site (`manage.py createsuperuser`). The two
  validations above were re-pointed at
  `accounts.tests.PasswordStorageTests`, which asserts exactly what
  `CustomerRegistrationTests` asserted, against such an account.
- Firebase's own password handling (hashing, reset emails, rate
  limiting) is Google's responsibility and is not evidenced here.

The original 2026-10-26 execution below stands as recorded; the test
names in the table are the current ones.

## Commands and actual results

```cmd
python manage.py check
```

Recorded result: System check identified no issues (0 silenced).

```cmd
python manage.py test accounts.tests.PasswordStorageTests
```

Recorded result: 7 tests passed, as `CustomerRegistrationTests` (see the
update below).

```cmd
python manage.py test
```

Recorded result: 60 tests passed in 29.710 seconds. No test failures were reported.

## Validation observations

- The registration test retrieves the newly created Django user from the database.
- The stored password differs from the submitted plaintext password.
- Django's `check_password()` method verifies the original password against the stored encoded value.
- The encoded value is checked for the expected password-hash format.
- The configured hasher assertion is exercised by the automated registration tests.

## Limitations

- These automated tests validate password storage representation and password-verification behavior. They do not constitute a full penetration test or independent cryptographic audit.
- The test suite runs against the database configured for the test environment. Production database behavior has not been independently audited.
- The results apply to the code and configuration used during this execution.
- The requirement IDs and test-case IDs above should be checked against the project's authoritative SRS and test plan before final submission.

---

# Validation Evidence — Issues #8, #9, #10, #11, #12, #17, #18, #24

- **Branch:** `feature/orders-payments-puneeth`
- **Execution date:** 2026-10-26
- **Local environment:** Linux, Python 3.12, Django 5.2.18, gunicorn 23.0.0, Node.js 24.21.0, npm 11.19.0, React 18.3.1, TypeScript 5.6, Vite 5.4.21, Vitest 2.1.9
- **Local test database:** Isolated SQLite via `config.settings_test`. The development MySQL database was not migrated and was not used for any test.
- **CI database:** MySQL 8.0 (`.github/workflows/main.yml`), which now runs the whole suite plus a missing-migration check.

## Automated test suite

```
cd backend
python manage.py check --settings=config.settings_test
# System check identified no issues (0 silenced).

python manage.py makemigrations --check --dry-run --settings=config.settings_test
# No changes detected

python manage.py test --settings=config.settings_test
# Ran 232 tests in 4.146s
# OK
```

```
cd frontend
npm run typecheck   # no errors
npm test            # 3 test files, 8 tests passed
npm run build       # built successfully (tsc --noEmit then vite build)
```

The suite grew from 95 to 232 backend tests over this work: 31 for issue
#10, 32 for #11, 55 for #12 and #24, 19 for #18, and the auth-API tests
that order history depends on.

## Test-case mapping and results

| Test case | Requirement | Implementation | Automated evidence | Result |
|---|---|---|---|---|
| TC-OBS-010 | OBS-F-010, OBS-F-011 Order placement and availability | `POST /api/orders/`, `GET /api/orders/availability/`; checkout page | `orders.tests.OrderApiTests` (14 tests), `AvailabilityLogicTests` | Pass |
| TC-OBS-012 | OBS-F-012, OBS-F-013 Payment and confirmation | `POST /api/payments/`; checkout and confirmation pages | `payments.tests.PaymentFlowTests` (17 tests) | Pass |
| Order viewing | OBS-F-014 Order history | `GET /api/orders/`; `/orders` page | `orders.tests.OrderHistoryTests` (6 tests) | Pass |
| Order cancellation | OBS-F-015 Cancel eligible orders | `POST /api/orders/<id>/cancel/`; cancel control on `/orders` | `orders.tests.OrderCancellationTests` (12 tests) | Pass |
| TC-OBS-016 | OBS-F-016 Book reviews | `/api/reviews/`; reviews section on the book details page | `reviews.tests` (32 tests across submission, display and editing) | Pass |
| TC-OBS-017 | OBS-F-017, OBS-F-018 Administrator catalogue and order management | `/api/admin/books/`, `/api/admin/orders/`; `/admin/books`, `/admin/orders` | `administration.tests.AdminCatalogueTests` (12), `AdminOrderManagementTests` (16), `AdminAuthorizationTests` (6) | Pass |
| Administrator customers and reports (#24) | SRS administrator capabilities (no separate OBS-F id) | `/api/admin/customers/`, `/api/admin/reports/sales/`; `/admin/customers`, `/admin/reports` | `administration.tests.AdminCustomerManagementTests` (12), `AdminSalesReportTests` (7) | Pass |
| TC-OBS-023 | OBS-NF-005 Scalability, 500 concurrent users | `backend/loadtest/load_test.py` | `Docs/evidence/tc-obs-023-load-test.{txt,json}` | **Read path pass; write path not validated — see below** |
| TC-OBS-024 | OBS-NF-006 Automated backups every 24 hours | `manage.py backup_data`, `manage.py verify_backups`, `GET /api/admin/backups/` | `operations.tests` (19 tests); `Docs/evidence/tc-obs-024-backup-evidence.txt` | Pass |

## End-to-end verification against a running server

`scripts/smoke_test.py` was run against gunicorn serving a throwaway
SQLite database, exercising the API over HTTP exactly as the React app
does. Full output: `Docs/evidence/integration-smoke-test.txt`.

All 56 checks passed, including:

- An order was placed, paid, and appeared in history with its paid state;
  stock fell from 12 to 10 on payment and returned to 12 on
  cancellation, with `refund_due` set. A second cancellation was refused
  with 409.
- A review was submitted (average 5.0), a duplicate was refused with 409,
  an out-of-range rating with 400, and the review was visible to a guest
  who could not themselves review.
- All five administrator endpoints returned 401 to a guest and 403 to a
  signed-in customer, and 200 to an administrator.
- A book was created with a punctuated ISBN that was normalized to
  `9781617294136`; a duplicate ISBN and a malformed ISBN were both
  refused with 400; a partial update changed stock without clearing the
  title; deleting a book that appears on an order was refused with 409.
- Skipping fulfilment (CONFIRMED to DELIVERED) was refused with 409,
  while PROCESSING, SHIPPED and DELIVERED each succeeded in order; a
  delivered order could not be cancelled by either the administrator or
  the customer.
- A customer was deactivated, could then no longer log in (401), and was
  reactivated; the administrator could not deactivate their own account.
- The sales report counted 1 revenue order of $42.50 and excluded the
  cancelled order; an invalid period was refused with 400.

## TC-OBS-023 — OBS-NF-005 scalability, measured

Target: gunicorn (4 workers x 16 threads) serving a throwaway SQLite
database on one machine. Harness: `backend/loadtest/load_test.py`, 500
concurrent sessions each with its own cookie jar, released together from
a barrier.

**Read path — catalogue, search, filter and categories (4000 requests):**

| Measure | Value |
|---|---|
| Concurrent users | 500 |
| Failed requests | 0 |
| Median response time | 1.4783 s |
| Mean | 1.3898 s |
| p95 | 2.0771 s |
| Max | 2.3036 s |
| Within the 3.0 s threshold | 4000 / 4000 (100.00%) |
| Throughput | 148.23 requests/second |

Result: **Pass** against the configured 3.0 s threshold.

**Write path — the same load plus one add-to-cart per user:** 490 of 500
add-to-cart requests returned HTTP 500. Reproduced with `DJANGO_DEBUG`
enabled at only 20 concurrent writes: `OperationalError: database is
locked`. SQLite permits one writer at a time, so this is a limitation of
the test substrate, not a defect in the application; the project baseline
is MySQL 8.0, which uses row-level locking.

### Limitations of this measurement

- SQLite, not MySQL. The read figures are therefore indicative, and the
  write path at 500 concurrent users is **not validated**. It must be
  re-measured against MySQL 8.0 before OBS-NF-005 can be claimed in
  full; the harness supports this unchanged via `--include-cart`.
- The load generator and the server shared one machine's CPU, so the
  response times include contention that a two-host setup would not have.
- Catalogue traffic only; checkout and payment were not included in the
  concurrent scenario.

## TC-OBS-024 — OBS-NF-006 automated backups, verified

`manage.py backup_data --trigger scheduled` was run against a live
database and then inspected three ways. Full output:
`Docs/evidence/tc-obs-024-backup-evidence.txt`.

- The run succeeded in 0.077 s, writing 13 records (7169 bytes):
  `books.book` 7, `orders.order` 2, `orders.orderitem` 2,
  `payments.payment` 2 — covering both the order data and the inventory
  (the catalogue carries the stock levels).
- The artifacts are Django fixtures plus `manifest.json` with per-dataset
  row counts and SHA-256 checksums, so a backup restores with
  `manage.py loaddata`.
- `manage.py verify_backups` reported the last successful backup 0.00
  hours ago against the 24-hour limit and exited 0.
- `GET /api/admin/backups/` reported `fresh: true`, `max_age_hours: 24`
  and the full execution record, and returned 403 to a customer.
- The `BackupRun` table is the execution record the requirement asks to
  be inspectable; records are retained even after old artifacts are
  pruned by `BACKUP_RETENTION_DAYS`.

### Limitations

- This validates the backup mechanism and the 24-hour check. It does not
  demonstrate a scheduler having run unattended for 24 hours in
  production: that evidence can only be collected after the cron entry
  (documented in `README.md` and the command's docstring) has been
  installed on the deployment host.
- A restore was not performed against a production-sized MySQL database.

## Notes on issues #8 and #9

The order-placement and payment code was implemented earlier on this
branch; the tests above were re-run after the issue #10 changes (which
added `paid_at` and `stock_reserved` to the payment path) and continue to
pass, together with the end-to-end verification recorded above.

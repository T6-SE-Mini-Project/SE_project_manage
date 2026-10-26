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
- **TC-OBS-022 scope:** Browser verification was performed as a guest. `CartApiTests.test_authenticated_cart_is_linked_to_user` verifies API-level cart association when an authenticated Django session is present, but it is not an end-to-end browser test. The React app has no login UI and does not integrate directly with the Django login page, so the registered-customer flow required by TC-OBS-022 has not been verified end to end.
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
| TC-OBS-021 | OBS-NF-003 | Verify that the stored credential differs from the original plaintext password and uses an encoded password hash. | `accounts.tests.CustomerRegistrationTests.test_password_is_hashed` | Pass |
| TC-OBS-030 | OBS-SR-003 | Verify that Django can validate the original password against the stored hash and that the stored value uses the configured password-hashing format. | `accounts.tests.CustomerRegistrationTests.test_password_is_hashed`, `accounts.tests.CustomerRegistrationTests.test_password_hash_uses_configured_hasher` | Pass |

## Commands and actual results

```cmd
python manage.py check
```

Recorded result: System check identified no issues (0 silenced).

```cmd
python manage.py test accounts.tests.CustomerRegistrationTests
```

Recorded result: 7 tests passed.

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

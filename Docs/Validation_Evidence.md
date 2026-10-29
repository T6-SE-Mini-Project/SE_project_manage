# Validation Evidence — Issues #4, #5, #6, #7, #13, #16

- Branch: `feature/book-browsing-details`
- Execution date: 2026-10-25
- Local environment: Windows, Python 3.13.7, Django 5.2.18, Node.js 22.19.0, npm 10.9.3, React 18.3.1, Vite 5.4.21, Vitest 2.1.9
- Local test database: isolated in-memory SQLite via `config.settings_test` (no credentials, no development MySQL access, no migrations applied to the development database)
- CI database: MySQL 8.0 (`.github/workflows/main.yml`); MySQL execution is pending CI/push

## Test-case mapping and results

| Test case | Requirement | Implementation | Automated evidence | Result |
| --- | --- | --- | --- | --- |
| TC-OBS-003 | OBS-F-003 Browse books | `GET /api/books/`; catalogue page at `/books` | `books.tests.BookApiTests.test_catalogue_returns_all_books_in_model_order`, `test_catalogue_returns_summary_fields` | Pass |
| TC-OBS-004 | OBS-F-004 Book search | `q` search over title, author, ISBN and description; catalogue search form | `BookSearchFilterTests.test_search_by_title`, `test_search_by_author`, `test_search_by_isbn`, `test_search_by_description_keyword` | Pass |
| TC-OBS-005 | OBS-F-005 Filter books | Category, author, min/max price and availability filters, individually and combined; catalogue filter form | `BookSearchFilterTests.test_filter_by_category`, `test_filter_by_author`, `test_filter_by_price_range`, `test_filter_by_availability`, `test_filters_combine` | Pass |
| TC-OBS-006 | OBS-F-006 Book details | `GET /api/books/<id>/`; details page at `/books/<id>` | `BookApiTests.test_details_return_book_information`, `test_unknown_book_returns_json_404` | Pass |
| TC-OBS-007 | OBS-F-007 Add book to cart | `POST /api/cart/items/`; one-click Add to cart on the details page | `CartApiTests.test_add_book_to_cart`, `test_add_same_book_increments_quantity`, `test_out_of_stock_book_is_rejected` | Pass |
| TC-OBS-008 | OBS-F-008 Manage cart items | `PATCH/DELETE /api/cart/items/<id>/`; cart page quantity and remove controls | `CartApiTests.test_update_cart_item_quantity`, `test_remove_cart_item`, `test_cart_is_scoped_to_the_session` | Pass |
| TC-OBS-009 | OBS-F-009 Calculate cart total | Server-side subtotal/total calculation; total shown on the cart page | `CartApiTests.test_total_reflects_prices_and_quantities`, `test_total_updates_when_contents_change` | Pass |
| TC-OBS-019 | OBS-NF-001 Search response time | Catalogue search endpoint | `books.tests.SearchPerformanceTests.test_search_response_time_target` | **Partially verified** — 20 sequential Django test-client requests over 40 SQLite rows passed the configured 3.0 s assertion: min=0.0008 s, p90=0.0023 s, max=0.0027 s; 20/20 within 3.0 s. This is not proof of the SRS OBS-NF-001 normal-operating-condition target or the related OBS-NF-005/AT-005 500-concurrent-user requirement; HTTP/WSGI, concurrent load, and MySQL performance remain unverified. |
| TC-OBS-022 | OBS-NF-004 Cart usability | Details page primary action | `frontend/src/components/AddToCartButton.test.jsx`; guest browser flow; `cart.tests.CartApiTests.test_authenticated_cart_is_linked_to_user` | **Partially verified** — the guest browser flow adds the book in one primary interaction, and the API test verifies authenticated-cart association. The registered-customer browser flow has **not** been verified end to end because the React app has no login UI and does not integrate directly with the Django login page. Complete end-to-end authenticated-customer usability is not claimed. |

## Commands and actual results

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

# Run from frontend/
npm test
# Test Files  1 passed (1)
# Tests       1 passed (1)

npm run build
# 44 modules transformed
# built in 881ms
```

## Browser and HTTP verification (temporary SQLite server, not the development database)

- Catalogue loaded 7 seeded books; search `q=clean` returned 1 book; category/availability/price filter returned the expected 2 books.
- Details endpoint returned the stored title, author, ISBN, publisher, publication date, price, stock and description; unknown book returned HTTP 404 JSON.
- Vite proxy at `http://127.0.0.1:5173/api/books/` returned the same catalogue, confirming frontend/backend integration.
- Guest browser flow at `http://127.0.0.1:5173/books`: catalogue → Clean Code details → one click on **Add to cart** → "Added to cart." and a **View cart** link. The cart then showed quantity 1, line total `$42.50`, and order total `$42.50`.
- Increasing the quantity to 2 updated the line total and order total to `$85.00`; removing the item showed the empty-cart state.
- CSRF/session flow: `GET /api/csrf/` issued a token; add, update, fetch and remove cart actions succeeded through the proxied session.

## Caveats

- Local backend tests and the performance measurement above use SQLite because no MySQL credentials were available and the development database must not be migrated. The same suite is configured to run against MySQL 8.0 in CI.
- **TC-OBS-019 scope:** the performance test made 20 sequential requests through Django's test client against 40 in-memory SQLite rows. The observed minimum was 0.0008 s, p90 was 0.0023 s, the maximum was 0.0027 s, and 20/20 requests completed within 3.0 s, so the configured assertion passed. This measurement does not exercise HTTP/WSGI, concurrent load, or MySQL, and it is not a 500-concurrent-user normal-load test. The SRS OBS-NF-001 normal-operating-condition target and the related OBS-NF-005/AT-005 scalability requirement therefore remain unverified.
- **TC-OBS-022 scope:** the browser verification was performed as a guest. `CartApiTests.test_authenticated_cart_is_linked_to_user` verifies API-level cart association when an authenticated Django session is present. It is not an end-to-end browser test. The React app has no login UI and does not integrate directly with the Django login page, so the registered-customer flow required by TC-OBS-022 has not been verified end to end.
- The cart is session-based and also associates with the authenticated user when a Django session is present. `CartApiTests.test_authenticated_cart_is_linked_to_user` covers registered-customer association.
- Prices are displayed in USD via `Intl.NumberFormat`; this is an assumption because the SRS does not specify a currency.


## Task #19 — Security Objective Validation

- **Branch:** `feature/issue-3-security-controls`
- **Test environment:** Windows, Python 3.13.14, Django 5.2.18, isolated in-memory SQLite via `config.settings_test`
- **Scope:** Confidentiality, integrity, authentication and authorization checks for the implemented cart and account functionality.

### Test-case results

| Test case | Objective | Evidence | Result |
|---|---|---|---|
| TC-OBS-025 | Confidentiality | `cart.tests.Task19SecurityObjectiveTests.test_025_other_session_cannot_read_another_carts_item` — a separate session receives an empty cart; the original session's cart remains intact. | Pass for cart session isolation; order confidentiality unverified. |
| TC-OBS-026 | Integrity | `cart.tests.Task19SecurityObjectiveTests.test_026_other_session_cannot_modify_cart_item` — a cross-session PATCH receives HTTP 404, and the stored cart-item quantity remains unchanged. | Pass for cart-item isolation; other protected data updates and order/payment changes unverified. |
| TC-OBS-027 | Authentication and authorization | `cart.tests.Task19SecurityObjectiveTests.test_027_anonymous_user_cannot_access_protected_page`, `test_027_authenticated_customer_can_access_protected_page`, and the existing login/admin authorization tests. | Pass for tested account and admin routes. |

### Commands and actual results

```powershell
.\.venv\Scripts\python.exe manage.py test cart.tests.Task19SecurityObjectiveTests --settings=config.settings_test -v 2
# Ran 22 tests in 0.172s
# OK

.\.venv\Scripts\python.exe manage.py test accounts.tests.CustomerLoginTests accounts.tests.AdminAuthorizationTests --settings=config.settings_test -v 2
# Ran 9 tests in 0.080s
# OK
```

### Limitations and follow-up

- The tests use an isolated in-memory SQLite database and do not modify the development database.
- The confidentiality and integrity tests cover session-scoped shopping carts. They do not establish protection of customer order records.
- No order-management endpoint or order model was identified in the inspected implementation. Order-related security validation remains unverified.
- The authentication checks cover the Django login-success page and admin route. The catalogue is public, so its successful access by anonymous users is expected.
- Results establish the behavior of the tested code paths, not the security of every application endpoint or a production deployment.

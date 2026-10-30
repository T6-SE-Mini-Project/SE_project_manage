# How this codebase works, and how to add to it

This is the guide for working on the Online Book Store. `README.md`
covers installing and running it; this file explains how the code is
organised, why it is organised that way, and what to do when you add a
feature.

---

## 1. The shape of the system

```
Browser
  │
  │  React + TypeScript (frontend/)
  │    pages/  ── render, hold form state
  │    hooks/  ── every server call (TanStack Query)
  │    api.ts  ── one typed fetch wrapper, CSRF + errors
  │    config.ts ─ reads VITE_* environment variables
  │
  │  HTTP, JSON, Firebase ID token (Bearer) + session cookie for the
  │  guest cart
  ▼
Django (backend/)
  urls.py      ── routes /api/<area>/ to an app
  views.py     ── parse the request, choose a status code
  services.py  ── the business rules, transactions, locking
  models.py    ── the data and its constraints
  serializers.py ─ turn models into JSON dicts
  │
  ▼
MySQL (Django ORM)
```

Two rules hold the whole thing together:

1. **The server decides.** The frontend never computes a total, decides
   whether an order may be cancelled, or assumes a user is an
   administrator. It asks, and renders the answer. The UI hiding a button
   is a convenience, never a control.
2. **Each layer has one job.** A view does not contain business rules; a
   service does not know about HTTP; a model does not format JSON.

---

## 2. The backend, layer by layer

### `config/` — the project's spine

| File | Responsibility |
|---|---|
| `env.py` | **The only module that reads the environment.** It loads `backend/.env`, validates and types each value, and exposes it as a module attribute. |
| `settings.py` | Django settings, built from `env`. It never calls `os.environ`. |
| `urls.py` | Mounts each app under `/api/<area>/`. |
| `http.py` | Shared JSON helpers: `read_json`, `json_error`, `login_required_api`, `staff_required_api`. |
| `cache.py` | **The only module that touches the cache.** The `cached_json` decorator, the namespaces, their time to live, and `invalidate`. |
| `throttle.py` | **The only module that counts requests.** The blanket middleware, the `throttle` decorator, and the limits themselves. |
| `settings_test.py` | Test-only settings: an isolated SQLite database, so tests never touch the development MySQL database. |
| `views.py` | Two infrastructure endpoints: `/api/csrf/` and the `/healthz/` liveness probe. |
| `tests.py` | Covers the deployment-only settings, which no other test exercises because the suite runs with `DEBUG=true`. |

**Adding a setting:** add it to `env.py` with a default and a comment,
expose it in `settings.py` if Django or an app needs it, and document it
in **all three** `.env.example` files (`backend/`, `frontend/`, root) plus
`backend/.env.production.example` and `render.yaml` when it matters in
production. Never read `os.environ` anywhere else — one place to look is
the point.

Settings that only apply in production (`DJANGO_DEBUG=false` with
`HTTPS_ENABLED=true`) are easy to break without noticing, since the test
suite runs with debug on. `config/tests.py` imports `config.settings` in a
subprocess under a production environment and asserts them, so add a case
there for any new one. See [Docs/Deployment.md](Docs/Deployment.md).

### Models — the data and its guarantees

Put invariants in the database, not only in Python. A rule enforced by a
`CheckConstraint` or `UniqueConstraint` cannot be bypassed by a future
code path, a management command or a data migration:

```python
class Meta:
    constraints = [
        models.UniqueConstraint(
            fields=["book", "user"],
            name="unique_review_per_customer_and_book",
        ),
        models.CheckConstraint(
            condition=models.Q(rating__gte=MIN_RATING)
            & models.Q(rating__lte=MAX_RATING),
            name="review_rating_within_range",
        ),
    ]
```

Order items snapshot `book_title` and `unit_price` at placement time, so
history stays truthful when the catalogue changes later. Prefer that over
a join when the past must stay fixed.

Note: a nested `Meta` class cannot see its enclosing class's attributes,
which is why `reviews/models.py` defines its rating bounds at module
level and re-exports them on the model.

### Services — the business rules

Anything involving more than one row, a decision, or money belongs in
`services.py`. Services are plain functions that take and return
objects, not requests and responses, so they can be called from a view, a
management command or a test alike.

Two conventions matter:

**Return outcomes, don't raise, when the "failure" is a normal result.**
A declined payment is an expected outcome that must still be recorded, so
`payments.services.process_order_payment` returns a `PaymentOutcome`.
Raising would roll back the failed-payment row that the order history
needs. Programming errors still raise.

```python
order, error = cancel_order(order, reason="Changed my mind")
if error is not None:
    return json_error(error, 409)
```

**Lock the rows you are about to decide on.** Two concurrent requests
must not both pass the same check:

```python
@transaction.atomic
def cancel_order(order, reason="", by_staff=False):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if not order.is_cancellable:
        return None, "This order can no longer be cancelled."
    ...
```

Stock is the clearest example: it is decremented only when payment
succeeds, `Order.stock_reserved` records that the order holds it, and
cancellation releases it exactly once.

### Views — HTTP only

A view parses input, calls a service, and maps the result to a status
code. Keep them boring:

```python
@require_POST
def order_cancel(request, pk):
    order = _get_scoped_order(request, pk)
    if order is None:
        return json_error("Order not found.", 404)

    data, error_response = read_json(request)
    if error_response is not None:
        return error_response

    cancelled, error = cancel_order(order, reason=str(data.get("reason", "")))
    if error is not None:
        return json_error(error, 409, order=serialize_order(order))

    return JsonResponse({"order": serialize_order(cancelled)})
```

Status codes used across the API:

| Code | Meaning |
|---|---|
| 200 / 201 | Success / created |
| 400 | Malformed or invalid input (often with an `errors` map) |
| 401 | Not signed in (the frontend sends the user to log in) |
| 403 | Signed in but not allowed (logging in again will not help) |
| 404 | Not found, or not visible to this caller |
| 409 | Conflict with current state: ineligible cancellation, unavailable stock, invalid transition |
| 402 | Payment declined |

Every error body has an `error` string, because the frontend's `ApiError`
reads that key. Field-level problems add `errors: {field: [messages]}`.

### Serializers — the JSON contract

Plain functions returning dicts. Two things to respect:

- **Decimals are strings** (`f"{amount:.2f}"`), never floats. Money must
  not pick up binary rounding on the way to the browser.
- **Send derived state the UI would otherwise have to infer.**
  `is_cancellable`, `status_display` and `allowed_transitions` are
  computed server-side so the UI cannot disagree with the server about
  what is possible.

Never expose a secret or a credential. Payments store only the last four
digits of a card; the full number is never persisted.

### Authentication

Identity comes from **Firebase**, not from a password this project holds.
The browser signs in with the Firebase SDK (`frontend/src/firebase.ts`)
and sends the ID token — an RS256 JWT — as `Authorization: Bearer <token>`
on every request. `accounts/middleware.py` verifies it, resolves the
Firebase uid to a Django user through `accounts.FirebaseIdentity`, and
assigns `request.user`. Everything downstream is unchanged: views,
decorators and query scoping only ever read `request.user`.

Three rules follow from that:

- **Never trust a uid, email or name from the request body.** They come
  from the verified token's claims or they do not count. The only module
  that reads a token is `accounts/firebase.py`; the only module that turns
  claims into a user is `accounts/services.py`.
- **Firebase cannot grant privileges.** `is_staff` lives on the Django
  user and is set from the command line (`manage.py grant_admin`) or the
  Django admin, never from anything the browser sends.
- **The session cookie is not authentication any more.** It keys the
  *guest* cart and guest orders, and `accounts/api_views.py` hands those
  over to the account on sign-in. Anything else keyed by session must be
  handed over there too — and must not follow one browser from one
  customer to the next (`SESSION_UID_KEY` is what prevents that). A
  session user is still honoured when no token is sent, but the only way
  to get one now is Django's admin login: the template registration and
  login pages were removed so that Firebase is the single credential
  path. Do not add another.

Tests mint real tokens with `accounts.tests_firebase.FirebaseTokenMixin`,
which signs them with a throwaway key and points the verifier's
certificate fetch at it, so no test has to mock verification away:

```python
class MyApiTests(FirebaseTokenMixin, TestCase):
    def test_something(self):
        response = self.client.get(
            reverse("order_collection"),
            HTTP_AUTHORIZATION=f"Bearer {self.make_token(uid='uid-1')}",
        )
```

### Authorization

Use the decorators from `config/http.py`, and apply them to the view, not
the URL:

```python
@require_GET
@staff_required_api          # 401 anonymous, 403 customer
def sales_report(request):
    ...
```

Scope every customer-facing query to the caller. `orders/views.py`
`_orders_for_request` is the pattern: an authenticated customer sees the
orders on their account plus their own guest orders from this session,
and nothing else. Never trust an id from the request to imply ownership.

A subtlety worth knowing: `POST /api/auth/signin/` cycles the session key
(for the same reason `django.contrib.auth.login()` does), and the cart and
guest orders are keyed by it. That endpoint therefore calls
`reassign_cart_session` and `claim_session_orders`. If you add anything
else keyed by session, hand it over there too.

### Caching

Every API read is cached in Redis, and the rule for keeping it correct is
the same one the frontend follows for its query cache: **a write
invalidates what it changed.**

A read declares what its answer depends on. `cached_json` goes *inside*
the authorization decorators, so a 401 or 403 is never cached:

```python
@require_GET
@staff_required_api
@cached_json(TTL_ADMIN, namespaces=[CUSTOMERS, ORDERS])
def customer_collection(request):
    ...
```

- **`namespaces`** are the bodies of data the response is built from.
  Name every one: the customer list carries order aggregates, so it
  depends on `ORDERS` as well as `CUSTOMERS`, and a new order must change
  it.
- **`scope`** is who may be served the same bytes. The default `SHARED`
  is for an answer that is identical for everyone allowed to see it.
  `PER_CALLER` is for anything that embeds the caller — a cart, an order
  history, a review list with `can_review` — and keys the entry by both
  the account and the session.

A write then names what it touched:

```python
# Cancelling releases the stock the order reserved.
invalidate(ORDERS, BOOKS)
```

Getting this wrong is how a customer sees stale stock, so when you add an
endpoint, ask the two questions in order: *what does this answer depend
on* (the namespaces), and *whose answer is it* (the scope). If a field in
the payload comes from a model no namespace covers, the response is not
cacheable yet — add a namespace for it and invalidate it on its writes.

Two things deliberately have no cache: `GET /api/auth/session/`, because
the login check must reflect a disabled account on the very next request,
and `GET /api/csrf/`, because it issues a token.

### Rate limiting

`RateLimitMiddleware` already counts every request — a generous limit for
reads, a tighter one for writes — so a new endpoint is limited the moment
it exists and needs nothing added.

Reach for `@throttle` only when *attempts* are the thing worth limiting
rather than volume: signing in, paying, posting a review. It goes below
the authorization decorators and above `cached_json`, so a refused
request is not served from the cache and a cached hit still counts:

```python
@login_required_api
@throttle(RATE_REVIEW, scope="review")
def _create_review(request):
    ...
```

Then the one question that decides whether the limit works at all: **what
does an attacker change between attempts?**

- `by=CALLER` (the default) counts per Firebase uid, falling back to the
  address for an anonymous caller. Right for anything a *signed-in*
  customer does, because the uid is fixed and unspoofable.
- `by=ADDRESS` counts per client address. Right when the caller's
  identity is itself the thing being attempted — sign-in and account
  creation arrive with a fresh uid each time, so a per-caller window
  there would never fill. This is what `accounts/middleware.py` uses, and
  why it limits provisioning *before* creating the Django user.

The cost of `ADDRESS` is that everybody behind one NAT shares a bucket,
so use it only where it is needed and keep the limit well clear of real
usage.

Two invariants to preserve:

- **A store failure allows the request.** `consume` swallows everything,
  because a limiter that returns 429 when Redis blinks turns a cache
  outage into a site outage. Keep that if you touch it.
- **Never limit `/healthz/`** (`EXEMPT_PREFIXES`), or a burst of traffic
  teaches Render that the service is down.

Limits are expressed as constants in `throttle.py`, never as literals at
the call site, and the test for a new limit asserts the behaviour — the
nth request is refused and an unrelated caller is not — rather than the
number.

---

## 3. The frontend, layer by layer

### `api.ts` — one way to call the server

It adds `Accept`/`Content-Type`, attaches the Firebase ID token as
`Authorization: Bearer …`, fetches and caches the CSRF token for writes,
and converts any non-2xx response into a typed `ApiError` carrying
`status` and the parsed `body`. Add a thin function per endpoint; never
call `fetch` from a component.

### `firebase.ts` and `hooks/useAuth.tsx` — who is signed in

`firebase.ts` is the only module that talks to the Firebase SDK. It
initializes lazily (an unconfigured `.env` must not blank the page) and
converts Firebase's error codes into messages a customer can act on.

`hooks/useAuth.tsx` has two layers, and the split matters:
`FirebaseAuthProvider` subscribes to the SDK once and holds the
**authId** — the Firebase uid — keeping it current through sign-in,
sign-out and hourly token refreshes; `useSession()` then asks the API who
that token resolves to. The account and `is_staff` are the server's
answer, never the browser's. `RequireAuth` waits for both before
deciding, which is what stops a signed-in customer being bounced to the
login page on every page load.

### `hooks/` — the data layer

Every server interaction is a TanStack Query hook. Components get data,
loading and error state from a hook and never manage it themselves.

- **Reads are queries**, keyed by a shared key from the `queryKeys` /
  `adminKeys` objects.
- **Writes are mutations** that invalidate exactly the keys they affect,
  so every screen showing that data updates at once. Cancelling an order
  invalidates orders *and* books, because releasing stock changes the
  catalogue.
- **Queries are typed with their error:** `useQuery<BookResponse, ApiError>`
  lets a component branch on `error.status === 404` without a cast.

```ts
export function useCancelOrder() {
  const queryClient = useQueryClient();

  return useMutation<OrderResponse, ApiError, { orderId: number; reason?: string }>({
    mutationFn: ({ orderId, reason }) => cancelOrder(orderId, reason ?? ""),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.order(data.order.id), data);
      void queryClient.invalidateQueries({ queryKey: queryKeys.orders() });
      void queryClient.invalidateQueries({ queryKey: ["books"] });
    },
  });
}
```

Hook files are grouped by area: `useBookStore.ts` (books, cart, orders,
payment), `useAuth.ts`, `useReviews.ts`, `useAdmin.ts`.

### `types.ts` — the contract in TypeScript

One interface per payload, matching the serializer. When you change a
serializer, change the interface in the same commit; `npm run build` runs
`tsc --noEmit` first, so a mismatch fails the build instead of the
browser.

Payload types used as query-string parameters are declared as `type`
aliases rather than `interface`, because only an object type alias gets
the implicit index signature the query-string builder needs.

### Pages and components

Pages own form state and routing; shared presentation lives in
`components/`. Server-driven state is read from hooks, not duplicated in
`useState`.

Conventions worth copying:

- Render the four states: pending, error, empty and loaded. Every page
  here does.
- Show the server's message on failure (`errorMessage`, `fieldError`
  from `errors.ts`) rather than a generic "something went wrong".
- When a write is refused with 409, show the reason and refetch, so the
  UI corrects itself instead of arguing with the server.
- Keep interactive controls real controls: `StarRating` renders radio
  inputs, so it works with a keyboard.
- Charts and figures: a single number is a stat tile, not a chart. Use
  one hue for a single measure, label the marks directly, keep grid and
  axes recessive, and provide a table view beside any chart.

---

## 4. Adding a feature, end to end

Say the issue is "customers can keep a wishlist".

**1. Branch from `main`.**

```bash
git checkout main && git pull
git checkout -b feature/wishlist-<yourname>
```

**2. Decide where it lives.** A new concern gets a new app; an extension
of an existing concern goes in that app.

```bash
cd backend && python manage.py startapp wishlist
```

Register it in `INSTALLED_APPS` and mount it in `config/urls.py`.

**3. Model it.** Fields, `Meta.ordering`, and the constraints that make
bad data impossible. Then:

```bash
python manage.py makemigrations wishlist
```

Review the generated migration and rename it to something readable. If
existing rows need values for a new field, add a data migration — see
`orders/migrations/0004_backfill_paid_orders.py`.

**4. Write the service**, if there are rules worth naming. Return
`(result, error)` or an outcome object; wrap multi-row work in
`transaction.atomic` and `select_for_update` what you decide on.

**5. Serialize it.** Strings for decimals, derived flags the UI needs.

**6. Write the view and URL.** Use `read_json`, `json_error` and the
authorization decorators. Scope queries to the caller.

**7. Test it.** In `wishlist/tests.py`, name the test after the behaviour
and the requirement it covers:

```python
class WishlistTests(TestCase):
    """Issue #NN / OBS-F-0NN: customers keep a wishlist."""

    def test_customer_can_only_see_their_own_wishlist(self):
        ...
```

Cover the happy path, each invalid input, and the authorization boundary
(anonymous, another customer, administrator). Run:

```bash
python manage.py test --settings=config.settings_test
python manage.py makemigrations --check --dry-run --settings=config.settings_test
```

**8. Add the frontend**, in this order: `types.ts` → `api.ts` → a hook →
the page. Then:

```bash
cd frontend && npm run typecheck && npm test && npm run build
```

**9. Verify it running**, not just under test. `scripts/smoke_test.py`
shows how to drive the API over HTTP against a throwaway database.

**10. Commit in logical pieces** with a message that says *why*, not just
what:

```
feat(wishlist): let customers save books for later (#NN)

Implements OBS-F-0NN. ...

- Why a unique (user, book) constraint: a wishlist is a set, and the
  database should say so.
```

**11. Open a pull request** that references the issue (`Closes #NN`),
lists what was implemented, and records the test results. Record
validation evidence for test-case issues in `Docs/Validation_Evidence.md`.

---

## 5. Conventions checklist

Before you open a pull request:

- [ ] No new `os.environ` read outside `config/env.py`; no secret in the repo
- [ ] Invariants expressed as database constraints, not only in Python
- [ ] Business rules in `services.py`, HTTP concerns in `views.py`
- [ ] Multi-row writes wrapped in a transaction, with rows locked before deciding
- [ ] Every customer-facing query scoped to the caller
- [ ] Admin-only views decorated with `staff_required_api`
- [ ] Money serialized as strings with two decimals
- [ ] Error responses carry an `error` key; field errors carry `errors`
- [ ] `types.ts` matches the serializer; every API call goes through a hook
- [ ] Pages render pending, error, empty and loaded states
- [ ] Tests cover the happy path, invalid input and the authorization boundary
- [ ] `python manage.py test --settings=config.settings_test` passes
- [ ] `makemigrations --check --dry-run` reports no changes
- [ ] `npm run typecheck`, `npm test` and `npm run build` pass
- [ ] Docs updated: `README.md` for setup or endpoints, this file for
      conventions, `Docs/Validation_Evidence.md` for test evidence

## 6. Where to look for an example

| If you are adding… | Read |
|---|---|
| A read-only endpoint with filters | `books/views.py` |
| Session-scoped state | `cart/` |
| A multi-step flow with locking | `orders/services.py`, `payments/services.py` |
| A model owned by a customer | `reviews/` |
| An administrator-only area | `administration/` |
| A scheduled job with an audit trail | `operations/` |
| A form-backed write with field errors | `administration/forms.py` + `views_books.py` |
| A page with a form and mutations | `frontend/src/pages/admin/AdminBooksPage.tsx` |
| A page that lists and acts on items | `frontend/src/pages/OrdersPage.tsx` |
| A figure or report | `frontend/src/pages/admin/AdminReportsPage.tsx` |

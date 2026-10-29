# Online Book Store

A web application for browsing and buying books, built for the Team T6
software-engineering mini project. Customers browse a catalogue, manage a
cart, place and pay for orders, review books and track their order
history; administrators manage the catalogue, process orders, manage
customer accounts and generate sales reports.

- **Backend:** Django 5.2 with the Django ORM on MySQL 8.0, serving a
  JSON API.
- **Frontend:** React 18 with TypeScript and Vite, with TanStack Query as
  the data layer.
- **Authentication:** Firebase Authentication (email/password and Google),
  verified on the backend as a JWT bearer token.
- **Cache:** Redis (Upstash over TLS) in front of every API read, with
  namespace invalidation on every write.
- **Deployment:** Docker Compose locally; in production the backend runs on
  Render (Docker) and the frontend on Vercel, against managed MySQL on Aiven.
  See [Docs/Deployment.md](Docs/Deployment.md).

## Live demo

- **Frontend:** <https://online-book-store-theta-seven.vercel.app>
- **Backend API:** <https://bookstore-api-7g5z.onrender.com>

The site is hosted on Vercel's free plan and proxies `/api/*` to the Render
backend, so the catalogue may take a few seconds to load if the backend has
been idle.

## Repository layout

```
backend/            Django project (all backend code lives here)
  config/           Settings, central env configuration, URL routing, HTTP
                    helpers, the Redis response cache
  accounts/         Firebase authentication: token verification, the uid to
                    user link, the JWT middleware and the session API
  books/            Book catalogue, search and filtering
  cart/             Session shopping cart
  orders/           Order placement, availability checks, history, cancellation
  payments/         Card payment integration and order confirmation
  reviews/          Book reviews and rating aggregation
  administration/   Administrator API: catalogue, orders, customers, reports
  operations/       Scheduled order and inventory backups
  loadtest/         Concurrent load-test harness (OBS-NF-005)
frontend/           React + TypeScript single-page app
  src/api.ts        Typed API client (CSRF, error handling)
  src/config.ts     Single place that reads frontend environment variables
  src/hooks/        TanStack Query hooks - the only way components call the API
  src/pages/        Route components, including pages/admin/
Docs/               SRS, architecture, test plan and validation evidence
scripts/            End-to-end smoke test
```

`instruction.md` explains how the pieces fit together and how to add a
new feature. Read it before your first change.

## Prerequisites

- Python 3.12 or newer
- Node.js 20 or newer (22 is used in CI)
- MySQL 8.0
- A C toolchain and MySQL client headers, for `mysqlclient`
  (`sudo apt install build-essential pkg-config default-libmysqlclient-dev`)

## Configuration

Every runtime value comes from the environment. Nothing is hard-coded and
no secret is committed.

- `backend/config/env.py` is the **only** module that reads the
  environment. It loads `backend/.env`, validates and types each value,
  and exposes it as a module attribute. `config/settings.py` and every
  other module import from there rather than touching `os.environ`.
- `frontend/src/config.ts` is the single place that reads Vite
  environment variables.
- `.env.example` files document every variable. Copy them and fill in
  your values; the real `.env` files are git-ignored.

```bash
cp backend/.env.example backend/.env     # backend + database settings
cp frontend/.env.example frontend/.env   # API base URL
cp .env.example .env                     # docker compose
```

Generate a secret key for `DJANGO_SECRET_KEY`:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

| Variable | Purpose | Default |
|---|---|---|
| `DJANGO_SECRET_KEY` | Django signing key | *required* |
| `DJANGO_DEBUG` | Development mode | `true` |
| `DJANGO_ALLOWED_HOSTS` | Permitted hosts, comma separated | `localhost,127.0.0.1` |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | MySQL credentials | *required* |
| `DB_HOST` / `DB_PORT` | MySQL location | `localhost` / `3306` |
| `DB_SSL_CA` | CA bundle path for a verified TLS database connection | *(empty)* |
| `DB_SSL_REQUIRED` | Require TLS without verifying the certificate | `false` |
| `DB_CONN_MAX_AGE` | Seconds a database connection is reused | `0` |
| `SESSION_COOKIE_AGE` | Guest cart session timeout (seconds) | `900` |
| `FIREBASE_PROJECT_ID` | Firebase project whose ID tokens are accepted | *(empty)* |
| `FIREBASE_TOKEN_LEEWAY` | Clock skew allowed when verifying a token (s) | `30` |
| `REDIS_URL` | Redis cache connection URL (`rediss://…`) | *(empty, no caching)* |
| `CACHE_ENABLED` | Serve API reads from the cache | `true` |
| `REDIS_TIMEOUT` | Seconds to wait for Redis before reading MySQL | `2` |
| `THROTTLE_ENABLED` | Enforce the rate limits | `true` |
| `THROTTLE_READ_RATE` | Reads allowed per caller per minute | `300` |
| `THROTTLE_WRITE_RATE` | Writes allowed per caller per minute | `60` |
| `TRUSTED_PROXY_COUNT` | Proxies in front of Django, for the client address | `0` |
| `CSRF_TRUSTED_ORIGINS` | Trusted cross-origin origins | *(empty)* |
| `HTTPS_ENABLED` | TLS terminated in front of Django | `false` |
| `BACKUP_DIR` | Where backups are written | `backend/backups` |
| `BACKUP_RETENTION_DAYS` | Days of backup artifacts to keep | `14` |
| `BACKUP_MAX_AGE_HOURS` | Maximum accepted backup age | `24` |
| `VITE_API_BASE_URL` | Frontend's API base URL | `/api` |
| `VITE_FIREBASE_API_KEY` | Firebase web API key | *required to sign in* |
| `VITE_FIREBASE_AUTH_DOMAIN` | Firebase auth domain | *required to sign in* |
| `VITE_FIREBASE_PROJECT_ID` | Firebase project id (same as the backend's) | *required to sign in* |
| `VITE_FIREBASE_STORAGE_BUCKET` | From the Firebase web config | *(empty)* |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | From the Firebase web config | *(empty)* |
| `VITE_FIREBASE_APP_ID` | From the Firebase web config | *(empty)* |

## Authentication

Customers sign in with **Firebase Authentication**, using either an email
address and password or their Google account. Firebase owns credentials:
no password ever reaches this project's backend, and no password is
stored in its database.

What the backend stores is the link. Each Firebase `uid` is recorded
against exactly one Django user (`accounts.FirebaseIdentity`), and
everything else — orders, carts, reviews, `is_staff` — hangs off that
user as before. The uid, not the email address, is the identity, so
changing an email in Firebase moves the address rather than creating a
second account.

The request path:

```
Browser  ── Firebase SDK sign-in ──>  Firebase
         <── ID token (RS256 JWT) ──
         ── Authorization: Bearer <token> ──>  Django
                                               accounts/middleware.py
                                               verifies the JWT, resolves
                                               the uid to request.user
```

`accounts/firebase.py` verifies every token against Google's **public**
signing certificates, so **no service-account JSON is needed** — only
`FIREBASE_PROJECT_ID`, which pins the token's audience and is what
rejects a token minted for a different Firebase project. The session
cookie still exists, but only as the key for a *guest* cart and guest
orders; it no longer authenticates anybody on the API.

Firebase is the **only** credential path. The Django template
registration and login pages that this project used to serve at
`/register/` and `/login/` are gone: a second way to create a password
account would have bypassed Firebase entirely. The backend now serves
only the JSON API and Django's admin site, and its root redirects to
`/admin/`. The admin site keeps its own password login, for the
administrator accounts made with `createsuperuser`.

### One-time Firebase setup

1. Create a project in the [Firebase console](https://console.firebase.google.com/).
2. Under **Authentication → Sign-in method**, enable **Email/Password**
   and **Google**.
3. Under **Authentication → Settings → Authorized domains**, add the
   domains the app is served from (`localhost` is there by default; add
   the Vercel domain for production).
4. Under **Project settings → General → Your apps**, add a Web app and
   copy its config into `frontend/.env` as the `VITE_FIREBASE_*`
   variables.
5. Put the same project id in `backend/.env` as `FIREBASE_PROJECT_ID`.

### Administrators

Firebase creates every account as an ordinary customer, and nothing in
the browser can grant itself administrator access. Sign in through the
app once, then promote the account from the command line:

```bash
cd backend
python manage.py grant_admin you@example.com      # --revoke to undo
```

An administrator is any account with `is_staff` set, exactly as before,
and existing accounts can still be promoted in the Django admin at
`/admin/`. An account that predates Firebase keeps its orders and its
`is_staff` flag when its owner first signs in through Firebase, provided
Firebase reports that email address as **verified** — which Google
sign-in does, and an unverified email/password sign-up does not.

## Caching

Every API read is cached in Redis — Upstash in production, over its
**TCP** endpoint (`rediss://`, TLS-only). `backend/config/cache.py` is
the only module that touches the cache, and it is opt-in: with no
`REDIS_URL` the cache backend is Django's dummy and every read goes to
MySQL, which is how the test suite and a plain local checkout run.

Set it up by copying the TCP URL from the Upstash console into
`backend/.env`:

```bash
REDIS_URL=rediss://default:<password>@<endpoint>.upstash.io:6379
```

Responses carry an `X-Cache: HIT|MISS` header, so a cached read is
visible in the browser's network panel or with `curl -i`.

### What is cached, and for how long

| Route | Time to live | Shared between callers |
|---|---|---|
| `GET /api/books/` | 60s | yes |
| `GET /api/books/<id>/` | 120s | yes |
| `GET /api/books/categories/` | 600s | yes |
| `GET /api/reviews/?book=` | 60s | no — carries `can_review` and your own review |
| `GET /api/cart/` | 30s | no |
| `GET /api/orders/`, `/api/orders/<id>/` | 30s / 60s | no |
| `GET /api/orders/availability/` | 15s | no |
| `GET /api/admin/*` | 30s | yes, between administrators |
| `GET /api/admin/reports/sales/` | 120s | yes, between administrators |

Not cached: `GET /api/auth/session/` (the login check must reflect a
disabled account or a dropped token on the very next request),
`GET /api/csrf/` and `/healthz/`.

### How it stays correct

The TTLs above are the safety net, not the mechanism. Each cached view
declares the **namespaces** its answer depends on (`books`, `orders`,
`cart`, `reviews`, `customers`, `backups`), and every write calls
`invalidate()` with what it changed — the same discipline as the
frontend's `invalidateQueries`. A version token per namespace goes into
the cache key, so replacing that token makes every entry built from it
unreachable in a single Redis write, however many entries there are.

Paying for an order, for instance, invalidates `orders`, `books` (stock
was reserved) and `cart`, so the catalogue shows the new stock on the
next request rather than up to a minute later.

Two consequences worth knowing:

- A write that bypasses the API — editing a book in the Django admin,
  `manage.py seed_books` — does not invalidate anything, so its change
  appears when the TTL lapses. That is why the TTLs are short.
- A cache failure is a cache miss. Every operation is wrapped, so a Redis
  timeout or outage makes the API slower, never broken. `CACHE_ENABLED=false`
  turns caching off without removing the URL.

## Rate limiting

The API counts requests per caller in one-minute windows and answers
`429` with a `Retry-After` header once a window is full.
`backend/config/throttle.py` is the only module that does the counting,
and it uses the same Redis as the cache so the limit is shared by every
worker and every Render instance.

| What is limited | Limit per minute | Counted per |
|---|---|---|
| Any read (`GET`, `HEAD`, `OPTIONS`) | 300 | caller |
| Any write (`POST`, `PUT`, `PATCH`, `DELETE`) | 60 | caller |
| `POST /api/auth/signin/` | 30 | **address** |
| First sign-in of an unknown Firebase uid | 30 | **address** |
| `POST /api/payments/…` | 10 | caller |
| Creating or editing a review | 10 | caller |

A **caller** is the Firebase uid when the request carries a valid token,
and the client address otherwise, so one customer's burst cannot lock
anybody else out — and a uid cannot be spoofed or changed by switching
network. The two sign-in limits are the exception: they are counted per
client address,
because a flood of sign-in attempts arrives with a different Firebase uid
every time and would never fill a per-caller window. Account creation is
limited in the middleware rather than in the view, so a refused attempt
does not leave a Django user behind.

Over a limit the response is:

```json
{"error": "Too many requests. Try again in 23 seconds.", "code": "rate_limited"}
```

with `Retry-After`, `X-RateLimit-Limit` and `X-RateLimit-Remaining`. The
frontend does not retry a `429` (`shouldRetry` in `src/api.ts`), so a
limited request surfaces the message instead of multiplying the load.

`/healthz/` and the static files are never counted, so a limit cannot
make Render think the service is down.

### Deploying behind a proxy

A per-address limit is only as good as the address. Django sees the last
proxy's address in `REMOTE_ADDR`, and the real client is somewhere in
`X-Forwarded-For` — which a client can also write to.
`TRUSTED_PROXY_COUNT` says how many entries at the right-hand end of that
header this deployment added, so the address is taken from that position
and anything the client appended is ignored.

- `0` locally and for any direct connection (use `REMOTE_ADDR`).
- `2` on Render for this project: the chain is browser → Vercel → Render.

Too low and every anonymous caller shares one bucket — the proxy's
address — so a handful of visitors could rate-limit the site. Too high
and a client can spoof the header and never be limited.

As with the cache, a failure is not an outage: if Redis is unreachable
the counter cannot be read, and the request is allowed through.
`THROTTLE_ENABLED=false` turns enforcement off; the test suite runs with
it off and switches it on per test.

## Running it locally

### 1. Database

```bash
mysql -u root -p -e "CREATE DATABASE online_book_store CHARACTER SET utf8mb4;"
```

### 2. Backend

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

cd backend
python manage.py migrate
python manage.py seed_books            # sample catalogue
python manage.py createsuperuser       # for the Django admin at /admin/
python manage.py runserver             # http://127.0.0.1:8000
```

`createsuperuser` creates a password account for Django's own admin site.
Customers (and administrators of the React app) sign in through Firebase
instead — see [Authentication](#authentication) above, and use
`manage.py grant_admin` to promote one.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev                            # http://127.0.0.1:5173
```

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`, so both
run on the same origin and the session cookie works without CORS.

### With Docker Compose

```bash
cp .env.example .env     # then edit the values
docker compose up --build
```

MySQL, the backend (gunicorn) and the frontend (nginx) start together;
nginx proxies `/api/` to the backend. The frontend is on port 80 and the
API on port 8000.

## API overview

All endpoints return JSON. Authentication is a Firebase ID token sent as
`Authorization: Bearer <token>`, which `frontend/src/api.ts` attaches to
every request. Writes also need the CSRF token from `GET /api/csrf/`,
which the same client handles automatically.

| Area | Endpoints |
|---|---|
| Accounts | `GET /api/auth/session/`, `POST /api/auth/signin\|logout/` |
| Books | `GET /api/books/`, `/api/books/categories/`, `/api/books/<id>/` |
| Cart | `GET /api/cart/`, `POST /api/cart/items/`, `PATCH\|DELETE /api/cart/items/<id>/` |
| Orders | `GET\|POST /api/orders/`, `GET /api/orders/availability/`, `GET /api/orders/<id>/`, `POST /api/orders/<id>/cancel/` |
| Payments | `POST /api/payments/` |
| Reviews | `GET\|POST /api/reviews/`, `PATCH\|DELETE /api/reviews/<id>/` |
| Admin catalogue | `GET\|POST /api/admin/books/`, `GET\|PATCH\|DELETE /api/admin/books/<id>/` |
| Admin orders | `GET /api/admin/orders/`, `GET /api/admin/orders/<id>/`, `POST /api/admin/orders/<id>/status/`, `POST /api/admin/orders/<id>/cancel/` |
| Admin customers | `GET /api/admin/customers/`, `GET /api/admin/customers/<id>/`, `POST /api/admin/customers/<id>/status/` |
| Admin reports | `GET /api/admin/reports/sales/`, `GET /api/admin/backups/` |

Everything under `/api/admin/` requires `is_staff`: anonymous callers get
401 and signed-in customers get 403. A token that is present but unusable
— expired, forged, or issued for another Firebase project — gets 401 from
the middleware on any endpoint, and a deactivated account gets 403.

### Payment test cards

Card payments go through a deterministic in-process gateway, so both
outcomes can be demonstrated. Any Luhn-valid number succeeds, except:

| Card number | Outcome |
|---|---|
| `4242 4242 4242 4242` | Succeeds |
| `4000 0000 0000 0002` | Declined |
| `4000 0000 0000 9995` | Insufficient funds |

## Order lifecycle

```
PENDING ──pay──> CONFIRMED ──> PROCESSING ──> SHIPPED ──> DELIVERED
   │                  │             │
   └──────────────────┴─────────────┴──> CANCELLED
```

Stock is reserved when payment succeeds, not when the order is placed, so
a failed payment never leaves the catalogue inconsistent. Cancelling an
order releases the stock it reserved. Only `PENDING`, `CONFIRMED` and
`PROCESSING` orders can be cancelled; the fulfilment steps run in order
and cannot be skipped or reversed.

## Testing

```bash
# Backend, against an isolated in-memory SQLite database
cd backend
python manage.py test --settings=config.settings_test

# Backend, against the configured MySQL database (as CI runs it)
python manage.py test

# Frontend
cd frontend
npm run typecheck
npm test
npm run build
```

`config.settings_test` never touches the development database, so it is
safe to run with shared MySQL credentials configured. It also disables
response caching, so no test is served another test's answer; the caching
behaviour itself is covered by `config/tests_cache.py` against a
local-memory cache. To run those same tests through the production Redis
backend:

```bash
redis-server --port 6399 --save '' --daemonize yes
OBS_TEST_REDIS_URL=redis://127.0.0.1:6399/0 \
    python manage.py test config.tests_cache --settings=config.settings_test
```

CI (`.github/workflows/main.yml`) runs the Django checks, a
missing-migration check and the full suite against MySQL 8.0, then the
frontend type-check, tests and build.

### End-to-end smoke test

`scripts/smoke_test.py` drives a running server over HTTP through the
whole customer and administrator flow, signing both accounts in through
Firebase's REST API exactly as the browser does. It therefore needs a
real Firebase project and its web API key. It writes data, so point it at
a throwaway database — the module docstring has the exact commands.

### Load testing

```bash
python backend/loadtest/load_test.py --users 500 --requests-per-user 2 \
    --base-url http://127.0.0.1:8000 --max-response-time 3.0
```

Measured results are in `Docs/evidence/`.

## Backups

Order and inventory data are backed up by a management command that
records every execution, so the schedule can be audited.

```bash
cd backend
python manage.py backup_data --trigger scheduled   # write a backup
python manage.py verify_backups                    # assert one ran in 24h
```

Schedule it at least once a day, for example with cron:

```cron
0 2 * * * cd /srv/online-book-store/backend && \
    /srv/online-book-store/.venv/bin/python manage.py backup_data \
    --trigger scheduled >> /var/log/obs-backup.log 2>&1
```

Each run writes Django fixtures plus a manifest with row counts and
SHA-256 checksums, so a backup restores with
`python manage.py loaddata <backup-dir>/books.book.json`. Administrators
can inspect the runs at `GET /api/admin/backups/` or on the Sales reports
screen.

## Deployment

Production runs the backend on **Render** and the frontend on **Vercel**,
against the existing managed **Aiven MySQL** instance.

- Frontend: <https://online-book-store-theta-seven.vercel.app>
- Backend API: <https://bookstore-api-7g5z.onrender.com>

| Piece | Config file | Committed |
|---|---|---|
| Render service (Docker, env vars, health check) | `render.yaml` | yes |
| Production backend values, for reference | `backend/.env.production.example` | yes, no secrets |
| Redis cache (Upstash TCP endpoint) | `REDIS_URL` on Render | no, it is a secret |
| Vercel build, `/api` rewrite, headers | `frontend/vercel.json` | yes |
| Production frontend values | `frontend/.env.production` | yes, no secrets |

Vercel rewrites `/api/*` to the Render service **server-side**, so the browser
only ever sees one origin. That is deliberate: the API's session cookie keys the
guest cart and guest orders, and `frontend/src/api.ts` sends
`credentials: "same-origin"`, so a cross-origin API would make that cookie
third-party — blocked by Safari and Firefox, and anything added to the cart
before signing in would be lost. (Sign-in itself would survive, since that
travels as a bearer token.) `VITE_API_BASE_URL` therefore stays `/api` in
production.

Values that must be set by hand after the first deploy:

- the backend's `FIREBASE_PROJECT_ID` on Render, and the matching
  `VITE_FIREBASE_*` variables in the Vercel project (Vercel injects them
  into the build, overriding the empty defaults in
  `frontend/.env.production`);
- the Vercel domain in the Firebase console, under **Authentication →
  Settings → Authorized domains** — Firebase refuses to sign anybody in
  from a domain not listed there;
- the backend's `REDIS_URL` on Render → the Upstash database's **TCP**
  endpoint (`rediss://…`, password included). Without it the API runs
  uncached;
- the backend's `CSRF_TRUSTED_ORIGINS` → the Vercel origin (the browser's
  origin is what Django's CSRF check sees, not the Render hostname);
- the Aiven credentials, which Render prompts for as it reads `render.yaml`.

Step-by-step instructions, the free-plan caveats (cold starts, ephemeral
backup storage) and a troubleshooting table are in
[Docs/Deployment.md](Docs/Deployment.md).

## Contributing

Read `instruction.md` first: it describes the request path, the
conventions each layer follows, and a worked example of adding a feature.
In short: one feature per branch, tests alongside the code, and a pull
request that references its issue.

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
- **Deployment:** Docker Compose locally; in production the backend runs on
  Render (Docker) and the frontend on Vercel, against managed MySQL on Aiven.
  See [Docs/Deployment.md](Docs/Deployment.md).

## Repository layout

```
backend/            Django project (all backend code lives here)
  config/           Settings, central env configuration, URL routing, HTTP helpers
  accounts/         Registration and login (template pages + JSON API)
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
| `SESSION_COOKIE_AGE` | Session inactivity timeout (seconds) | `900` |
| `CSRF_TRUSTED_ORIGINS` | Trusted cross-origin origins | *(empty)* |
| `HTTPS_ENABLED` | TLS terminated in front of Django | `false` |
| `BACKUP_DIR` | Where backups are written | `backend/backups` |
| `BACKUP_RETENTION_DAYS` | Days of backup artifacts to keep | `14` |
| `BACKUP_MAX_AGE_HOURS` | Maximum accepted backup age | `24` |
| `VITE_API_BASE_URL` | Frontend's API base URL | `/api` |

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
python manage.py createsuperuser       # an administrator account
python manage.py runserver             # http://127.0.0.1:8000
```

An administrator is any account with `is_staff` set — `createsuperuser`
makes one, and existing accounts can be promoted in the Django admin at
`/admin/`.

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

All endpoints return JSON. Writes need the CSRF token from
`GET /api/csrf/`, which the frontend client handles automatically.
Authentication is Django's session cookie.

| Area | Endpoints |
|---|---|
| Accounts | `GET/POST /api/auth/session\|login\|logout\|register/` |
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
401 and signed-in customers get 403.

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
safe to run with shared MySQL credentials configured.

CI (`.github/workflows/main.yml`) runs the Django checks, a
missing-migration check and the full suite against MySQL 8.0, then the
frontend type-check, tests and build.

### End-to-end smoke test

`scripts/smoke_test.py` drives a running server over HTTP through the
whole customer and administrator flow. It writes data, so point it at a
throwaway database — the module docstring has the exact commands.

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

| Piece | Config file | Committed |
|---|---|---|
| Render service (Docker, env vars, health check) | `render.yaml` | yes |
| Production backend values, for reference | `backend/.env.production.example` | yes, no secrets |
| Vercel build, `/api` rewrite, headers | `frontend/vercel.json` | yes |
| Production frontend values | `frontend/.env.production` | yes, no secrets |

Vercel rewrites `/api/*` to the Render service **server-side**, so the browser
only ever sees one origin. That is deliberate: authentication is a Django
session cookie and `frontend/src/api.ts` sends `credentials: "same-origin"`, so
a cross-origin API would make the session cookie third-party — blocked by
Safari and Firefox. `VITE_API_BASE_URL` therefore stays `/api` in production.

Two values must be set by hand after the first deploy:

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

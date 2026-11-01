# Billing Address Feature

## Scope

The checkout flow is now:

```text
Catalogue -> Cart -> Billing address -> Order confirmation
```

The existing project had no shipping-address feature and no payment-gateway
integration. Therefore:

- The "Billing address is same as shipping address" checkbox is intentionally
  omitted. There is no shipping address model or form to copy from.
- Payment remains explicitly unimplemented. Orders are created with the status
  `pending_payment`; no card number, CVV, or banking credential is collected,
  transmitted, or stored.

## Currency

All catalogue, cart, checkout, and order prices are formatted in Indian rupees
using `Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" })` in
`frontend/src/format.js`. The seeded sample catalogue uses realistic INR
amounts (for example, Clean Code is ₹2,499.00).

## Data model

The new `orders` Django app contains:

### `BillingAddress`

| Field | Rules |
| --- | --- |
| `user` | Optional FK to the authenticated customer; saved addresses are scoped to this customer |
| `full_name` | Required, whitespace-normalised, max 150 |
| `phone_number` | Required, exactly 10 digits after spaces/hyphens are removed |
| `email` | Required, valid email format, lower-cased |
| `address_line1` | Required, max 255 |
| `address_line2` | Optional, max 255 |
| `city` | Required, max 100 |
| `state` | Required, max 100 |
| `postal_code` | Required, exactly 6 digits (PIN code) |
| `country` | Required, defaults to `India` |
| `fingerprint` | SHA-256 of normalised values; used to reuse an identical saved address |

Guest addresses are order snapshots with `user = NULL`. Authenticated customers
who tick **Save this address for future orders** get a reusable address; a
second identical submission reuses the existing row instead of creating a
duplicate.

### `Order`

- `reference`: UUID shown to the customer as a short order reference
- `user`: optional owner for authenticated orders
- `session_key`: owner scope for guest orders
- `billing_address`: required FK to the address used for the order
- `status`: defaults to `pending_payment`
- `total`: server-calculated order total

### `OrderItem`

Snapshots the book title, unit price, and quantity at checkout time, and links
to the book with `PROTECT` so historical orders keep their data.

## API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/auth/session/` | Returns whether the current session is authenticated and the customer's public account fields |
| `GET` | `/api/billing-addresses/` | Lists only the authenticated customer's saved addresses; anonymous requests receive `401` |
| `POST` | `/api/checkout/` | Validates billing data, creates the order, links the address, removes the cart contents, and returns the order |
| `GET` | `/api/orders/<id>/` | Returns an order only to its owner (authenticated customer or the guest session that created it) |

Checkout request body:

```json
{
  "billing_address": {
    "full_name": "Ananya Sharma",
    "phone_number": "9876543210",
    "email": "ananya.sharma@example.com",
    "address_line1": "12 MG Road",
    "address_line2": "Near City Library",
    "city": "Bengaluru",
    "state": "Karnataka",
    "postal_code": "560001",
    "country": "India"
  },
  "save_address": false
}
```

Validation failures return HTTP `400` with an `errors` object keyed by field
name. Stock failures return HTTP `409`. Empty carts and malformed JSON return
HTTP `400`. Unauthorised address or order access returns `401`/`404` without
leaking whether another customer's record exists.

## Ownership and security

- Saved address listing is filtered by `request.user`.
- Order detail access is checked against the order owner or the guest session
  key.
- CSRF protection uses the existing `X-CSRFToken` request flow in
  `frontend/src/api.js`.
- No payment credentials are accepted by any endpoint or stored in any model.

## Payment integration point

`orders/services.py` contains an explicit `PAYMENT INTEGRATION POINT` comment in
`place_order()`. A future payment milestone should:

1. Collect payment through a provider-hosted or provider-secure component.
2. Never send card data to these Django endpoints.
3. Update the created order from `pending_payment` to `confirmed` only after
   provider confirmation.

Until then, the confirmation page states clearly that no payment was taken.

## Migrations

`orders/migrations/0001_initial.py` creates `BillingAddress`, `Order`, and
`OrderItem`, including the order-book uniqueness constraint and quantity check.

Apply against MySQL 8.0 with the normal project settings:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

## Running locally

The repository's `config.settings` uses MySQL. The local development environment
for this demonstration had no MySQL credentials available, so the automated
tests and demo used `config.settings_test` with a temporary SQLite database.
The CI workflow still runs the suite against MySQL 8.0.

```powershell
# MySQL application
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver

# Isolated automated tests (SQLite)
.\.venv\Scripts\python.exe manage.py test accounts books cart orders --settings=config.settings_test

# Frontend
cd frontend
npm test
npm run build
npm run dev
```

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`.

## Tests

Backend coverage in `orders/tests.py`:

- valid submission, order creation, address persistence, stock decrement, cart
  clearing
- missing required fields
- invalid phone number
- invalid email
- invalid 6-digit PIN code
- phone numbers containing spaces or hyphens
- empty cart
- malformed JSON and invalid `save_address` type
- insufficient stock
- authenticated save/reuse of an address
- guest save flag not creating a saved address
- saved-address ownership isolation
- order access isolation by session and by customer

Frontend coverage in `frontend/src/billingValidation.test.js` covers required
fields, phone/email/PIN validation, optional address line 2, and value
normalisation.

## Editing this feature

The feature is ordinary source code; no generated bundle or screenshot is
required. Use the existing `feature/billing-address` branch and open a pull
request for review.

### Add or change a form field

1. Update the field in `orders/models.py` (`BillingAddress`).
2. Create a migration:
   `python manage.py makemigrations orders`
3. Add the field to `BillingAddressForm.Meta.fields` in `orders/forms.py`. If it
   needs custom messages or normalisation, add an explicit form field there.
4. Add the field to `EMPTY_BILLING_ADDRESS`, `normalizeBillingAddress()` and
   `validateBillingAddress()` in `frontend/src/billingValidation.js`.
5. Add the input definition to `ADDRESS_FIELDS` in
   `frontend/src/pages/CheckoutPage.jsx`.
6. If the order response should expose the field, update
   `orders/serializers.py` and, if it should be visible, the address block in
   `frontend/src/pages/OrderConfirmationPage.jsx`.
7. Extend `orders/tests.py` and `frontend/src/billingValidation.test.js`.

### Change backend validation

- Phone and PIN regexes live in `orders/models.py` as
  `PHONE_NUMBER_VALIDATOR` and `PIN_CODE_VALIDATOR`.
- `BillingAddressForm` in `orders/forms.py` controls the API's field-level error
  messages.
- Keep the client-side rules in `frontend/src/billingValidation.js` aligned so
  users see errors before submitting. Server validation is authoritative.

### Change the API

- Routes: `orders/urls.py` (mounted under `/api/` in `config/urls.py`).
- Request handling and ownership checks: `orders/views.py`.
- Order creation, address deduplication and the payment integration point:
  `orders/services.py`.
- Response shapes: `orders/serializers.py`.
- Frontend calls: `frontend/src/api.js`.

Run the full suite after any change:

```powershell
.\.venv\Scripts\python.exe manage.py test accounts books cart orders --settings=config.settings_test
cd frontend
npm test
npm run build
```

## Demonstration video

The recorded demonstration is stored at:

```text
Docs/demos/billing-address-demo.mp4
```

(On Windows the folder name is case-insensitive, so `docs/demos/...` resolves to
the same file.)

It is 1 minute 56 seconds at 1280x800 (H.264, about 4.2 MB), comfortably below
GitHub's 100 MB per-file limit, so Git LFS is not required. The video is a
recording of the real checkout flow plus captured source, test and database
evidence; the editable source files are all included in the repository.


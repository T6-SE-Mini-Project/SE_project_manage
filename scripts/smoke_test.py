"""End-to-end smoke test of the customer and administrator features.

Exercises the running application over HTTP the way the React app does:
order placement, payment, history and cancellation (issue #10), book
reviews (issue #11), administrator catalogue and order management
(issue #12), customer management and sales reports (issue #24) and the
backup records (issue #18), including the authorization boundary that
keeps customers out of the administrator API.

It writes data, so point it at a throwaway database, never a shared one.

    # Terminal 1 - serve a throwaway SQLite database
    cd backend
    export TEST_SQLITE_NAME=/tmp/obs-smoke.sqlite3
    python manage.py migrate --settings=config.settings_test
    python manage.py seed_books --settings=config.settings_test
    python manage.py createsuperuser --settings=config.settings_test \
        --username storeadmin --email storeadmin@example.com
    DJANGO_SETTINGS_MODULE=config.settings_test \
        gunicorn config.wsgi:application --bind 127.0.0.1:8098

    # Terminal 2
    python scripts/smoke_test.py --base-url http://127.0.0.1:8098 \
        --admin-username storeadmin --admin-password <password>

Exits non-zero when any check fails.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar

failures = []

BASE = ["http://127.0.0.1:8098"]
ADMIN = {"username": "storeadmin", "password": ""}


class Client:
    def __init__(self, name):
        self.name = name
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar))

    def token(self):
        self.opener.open(f"{BASE[0]}/api/csrf/", timeout=30).read()
        return next((c.value for c in self.jar if c.name == "csrftoken"), "")

    def call(self, method, path, payload=None):
        headers = {"Accept": "application/json"}
        data = None
        if method not in ("GET", "HEAD"):
            headers["X-CSRFToken"] = self.token()
            headers["Referer"] = BASE[0]
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload or {}).encode()
        req = urllib.request.Request(f"{BASE[0]}{path}", data=data, method=method, headers=headers)
        try:
            with self.opener.open(req, timeout=30) as resp:
                body = resp.read().decode()
                return resp.status, (json.loads(body) if body.strip() else {})
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()
            try:
                return exc.code, json.loads(body)
            except json.JSONDecodeError:
                return exc.code, {"raw": body[:200]}

def check(label, got, want):
    ok = got == want
    if not ok:
        failures.append(f"{label}: expected {want}, got {got}")
    print(f"  [{'OK ' if ok else 'FAIL'}] {label} -> {got}")


def run_checks():
    """Run every check in order against the configured base URL."""
    customer = Client("customer")
    admin = Client("admin")

    print("\n== Issue #10: order placement, history and cancellation ==")
    status, body = customer.call("POST", "/api/auth/register/", {
        "username": "smokecustomer", "email": "smoke@example.com",
        "password1": "SmokePass12345", "password2": "SmokePass12345"})
    check("register customer", status, 201)

    status, books = customer.call("GET", "/api/books/")
    book = books["books"][0]
    stock_before = book["stock_quantity"]
    print(f"  book under test: {book['title']} (stock {stock_before})")

    check("add to cart", customer.call("POST", "/api/cart/items/", {"book_id": book["id"], "quantity": 2})[0], 200)
    status, placed = customer.call("POST", "/api/orders/")
    check("place order", status, 201)
    order_id = placed["order"]["id"]
    check("new order is pending", placed["order"]["status"], "PENDING")
    check("pending order is cancellable", placed["order"]["is_cancellable"], True)

    status, paid = customer.call("POST", "/api/payments/", {
        "order_id": order_id, "card_number": "4242424242424242",
        "cvc": "123", "expiry_month": 12, "expiry_year": 2099})
    check("pay order", status, 200)
    check("order confirmed", paid["order"]["status"], "CONFIRMED")

    status, history = customer.call("GET", "/api/orders/")
    check("history lists the order", history["count"], 1)
    check("history shows paid state", history["orders"][0]["is_paid"], True)

    status, after_pay = customer.call("GET", f"/api/books/{book['id']}/")
    check("stock reserved by payment", after_pay["book"]["stock_quantity"], stock_before - 2)

    status, cancelled = customer.call("POST", f"/api/orders/{order_id}/cancel/", {"reason": "Smoke test"})
    check("cancel confirmed order", status, 200)
    check("order cancelled", cancelled["order"]["status"], "CANCELLED")
    check("refund flagged", cancelled["order"]["refund_due"], True)
    status, restored = customer.call("GET", f"/api/books/{book['id']}/")
    check("stock released by cancellation", restored["book"]["stock_quantity"], stock_before)
    check("second cancellation refused", customer.call("POST", f"/api/orders/{order_id}/cancel/")[0], 409)

    print("\n== Issue #11: book reviews ==")
    status, review = customer.call("POST", "/api/reviews/", {
        "book_id": book["id"], "rating": 5, "title": "Great", "comment": "Recommended."})
    check("submit review", status, 201)
    review_id = review["review"]["id"]
    check("average rating", review["summary"]["average_rating"], "5.0")
    check("duplicate review refused", customer.call("POST", "/api/reviews/", {"book_id": book["id"], "rating": 3})[0], 409)
    check("invalid rating refused", customer.call("PATCH", f"/api/reviews/{review_id}/", {"rating": 9})[0], 400)
    check("edit own review", customer.call("PATCH", f"/api/reviews/{review_id}/", {"rating": 4})[0], 200)
    status, listing = Client("guest").call("GET", f"/api/reviews/?book={book['id']}")
    check("reviews are public", status, 200)
    check("guest cannot review", listing["can_review"], False)
    check("review visible to guest", len(listing["reviews"]), 1)

    print("\n== Issues #12 and #24: administrator-only access ==")
    for path in ("/api/admin/books/", "/api/admin/orders/", "/api/admin/customers/",
                 "/api/admin/reports/sales/", "/api/admin/backups/"):
        check(f"customer blocked from {path}", customer.call("GET", path)[0], 403)
        check(f"guest blocked from {path}", Client("g").call("GET", path)[0], 401)

    check("admin login", admin.call("POST", "/api/auth/login/", {
        "username": "storeadmin", "password": "AdminPass12345"})[0], 200)

    print("\n== Issue #12: catalogue management ==")
    status, created = admin.call("POST", "/api/admin/books/", {
        "title": "Smoke Test Title", "author": "Smoke Author", "isbn": "978-1617294136",
        "description": "Added by the smoke test.", "category": "Testing",
        "price": "19.99", "stock_quantity": 4, "publisher": "Test Press",
        "publication_date": "2020-01-01", "cover_image_url": ""})
    check("create book", status, 201)
    new_id = created["book"]["id"]
    check("isbn normalized", created["book"]["isbn"], "9781617294136")
    check("duplicate isbn refused", admin.call("POST", "/api/admin/books/", {
        "title": "Dupe", "author": "A", "isbn": "9781617294136", "category": "Testing",
        "price": "9.99", "stock_quantity": 1, "description": "", "publisher": "",
        "publication_date": None, "cover_image_url": ""})[0], 400)
    check("bad isbn refused", admin.call("POST", "/api/admin/books/", {
        "title": "Bad", "author": "A", "isbn": "nope", "category": "Testing",
        "price": "9.99", "stock_quantity": 1, "description": "", "publisher": "",
        "publication_date": None, "cover_image_url": ""})[0], 400)
    status, updated = admin.call("PATCH", f"/api/admin/books/{new_id}/", {"stock_quantity": 12})
    check("update stock", updated["book"]["stock_quantity"], 12)
    check("title preserved by partial update", updated["book"]["title"], "Smoke Test Title")
    check("delete unordered book", admin.call("DELETE", f"/api/admin/books/{new_id}/")[0], 200)
    check("delete ordered book refused", admin.call("DELETE", f"/api/admin/books/{book['id']}/")[0], 409)

    print("\n== Issue #12: order management ==")
    check("add to cart again", customer.call("POST", "/api/cart/items/", {"book_id": book["id"], "quantity": 1})[0], 200)
    status, placed2 = customer.call("POST", "/api/orders/")
    order2 = placed2["order"]["id"]
    customer.call("POST", "/api/payments/", {"order_id": order2, "card_number": "4242424242424242",
                                            "cvc": "123", "expiry_month": 12, "expiry_year": 2099})
    status, orders = admin.call("GET", "/api/admin/orders/")
    check("admin sees all orders", orders["count"] >= 2, True)
    check("skipping fulfilment refused", admin.call("POST", f"/api/admin/orders/{order2}/status/", {"status": "DELIVERED"})[0], 409)
    for step in ("PROCESSING", "SHIPPED", "DELIVERED"):
        check(f"advance to {step}", admin.call("POST", f"/api/admin/orders/{order2}/status/", {"status": step})[0], 200)
    check("delivered order cannot be cancelled", admin.call("POST", f"/api/admin/orders/{order2}/cancel/")[0], 409)
    check("customer cannot cancel delivered order", customer.call("POST", f"/api/orders/{order2}/cancel/")[0], 409)

    print("\n== Issue #24: customers and sales reports ==")
    status, customers = admin.call("GET", "/api/admin/customers/")
    check("customer list", status, 200)
    row = next(c for c in customers["customers"] if c["username"] == "smokecustomer")
    check("order count aggregated", row["order_count"], 2)
    check("own account cannot be deactivated", admin.call("POST", f"/api/admin/customers/{next(c['id'] for c in customers['customers'] if c['username'] == 'storeadmin')}/status/", {"is_active": False})[0], 400)
    check("deactivate customer", admin.call("POST", f"/api/admin/customers/{row['id']}/status/", {"is_active": False})[0], 200)
    check("deactivated customer cannot log in", Client("x").call("POST", "/api/auth/login/", {"username": "smokecustomer", "password": "SmokePass12345"})[0], 401)
    check("reactivate customer", admin.call("POST", f"/api/admin/customers/{row['id']}/status/", {"is_active": True})[0], 200)

    status, report = admin.call("GET", "/api/admin/reports/sales/")
    check("sales report", status, 200)
    r = report["report"]["revenue"]
    print(f"  revenue={r['total']} orders={r['order_count']} aov={r['average_order_value']} items={r['items_sold']}")
    check("cancelled order excluded from revenue", r["order_count"], 1)
    check("bad period refused", admin.call("GET", "/api/admin/reports/sales/?start=notadate")[0], 400)

    print("\n== Issue #18: backups ==")
    status, backups = admin.call("GET", "/api/admin/backups/")
    check("backup endpoint", status, 200)
    print(f"  fresh={backups['freshness']['fresh']} runs={len(backups['runs'])}")

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:8098")
    parser.add_argument("--admin-username", default="storeadmin")
    parser.add_argument("--admin-password", required=True)
    args = parser.parse_args(argv)

    BASE[0] = args.base_url.rstrip("/")
    ADMIN["username"] = args.admin_username
    ADMIN["password"] = args.admin_password

    run_checks()

    print("\n" + ("ALL SMOKE CHECKS PASSED" if not failures
                   else f"{len(failures)} FAILURES"))
    for failure in failures:
        print("  -", failure)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

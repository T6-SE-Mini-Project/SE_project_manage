"""Tests for the administrator API.

Covers issue #12 (catalogue and order management, OBS-F-017/OBS-F-018,
TC-OBS-017) and issue #24 (customer management and sales reports),
including the rule that customer accounts can never reach
administrator-only operations.
"""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from books.models import Book
from orders.models import Order, OrderItem
from payments.models import Payment


def book_data(**overrides):
    data = {
        "title": "Admin Book",
        "author": "Admin Author",
        "isbn": "9780132350884",
        "description": "A book used by administrator tests.",
        "category": "Fiction",
        "price": Decimal("30.00"),
        "stock_quantity": 8,
    }
    data.update(overrides)
    return data


class AdminTestCase(TestCase):
    """Shared fixtures: one administrator and one ordinary customer."""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            username="bookadmin",
            email="admin@example.com",
            password="AdminPass123",
            is_staff=True,
        )
        self.customer = User.objects.create_user(
            username="shopper",
            email="shopper@example.com",
            password="ShopperPass123",
        )
        self.admin_client = Client()
        self.admin_client.force_login(self.admin)
        self.customer_client = Client()
        self.customer_client.force_login(self.customer)

    def post_json(self, client, url, payload):
        return client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def patch_json(self, client, url, payload):
        return client.patch(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )


class AdminAuthorizationTests(AdminTestCase):
    """Unauthorized customers cannot access administrator operations."""

    def admin_urls(self):
        book = Book.objects.create(**book_data())
        order = Order.objects.create(
            session_key="adminsession",
            total_amount=Decimal("10.00"),
        )

        return [
            ("get", reverse("admin_book_collection")),
            ("get", reverse("admin_book_detail", args=[book.pk])),
            ("get", reverse("admin_order_collection")),
            ("get", reverse("admin_order_detail", args=[order.pk])),
            ("get", reverse("admin_customer_collection")),
            (
                "get",
                reverse("admin_customer_detail", args=[self.customer.pk]),
            ),
            ("get", reverse("admin_sales_report")),
            ("get", reverse("admin_backup_collection")),
        ]

    def test_anonymous_callers_are_unauthorized(self):
        anonymous = Client()

        for method, url in self.admin_urls():
            with self.subTest(url=url):
                response = getattr(anonymous, method)(url)
                self.assertEqual(response.status_code, 401)
                self.assertIn("error", response.json())

    def test_customers_are_forbidden(self):
        for method, url in self.admin_urls():
            with self.subTest(url=url):
                response = getattr(self.customer_client, method)(url)
                self.assertEqual(response.status_code, 403)
                self.assertIn(
                    "Administrator privileges",
                    response.json()["error"],
                )

    def test_administrators_are_allowed(self):
        for method, url in self.admin_urls():
            with self.subTest(url=url):
                response = getattr(self.admin_client, method)(url)
                self.assertEqual(response.status_code, 200)

    def test_customer_cannot_create_a_book(self):
        response = self.post_json(
            self.customer_client,
            reverse("admin_book_collection"),
            book_data(isbn="9780201633610", price="12.00"),
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Book.objects.filter(isbn="9780201633610").exists())

    def test_customer_cannot_change_an_order_status(self):
        order = Order.objects.create(
            session_key="s",
            status=Order.STATUS_CONFIRMED,
            total_amount=Decimal("10.00"),
        )

        response = self.post_json(
            self.customer_client,
            reverse("admin_order_status", args=[order.pk]),
            {"status": "SHIPPED"},
        )

        self.assertEqual(response.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_CONFIRMED)

    def test_customer_cannot_deactivate_an_account(self):
        response = self.post_json(
            self.customer_client,
            reverse("admin_customer_status", args=[self.admin.pk]),
            {"is_active": False},
        )

        self.assertEqual(response.status_code, 403)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)


class AdminCatalogueTests(AdminTestCase):
    """TC-OBS-017 / OBS-F-017: administrators manage the book catalogue."""

    def setUp(self):
        super().setUp()
        self.book = Book.objects.create(**book_data())

    def test_catalogue_list_includes_management_fields(self):
        response = self.admin_client.get(reverse("admin_book_collection"))

        self.assertEqual(response.status_code, 200)
        body = response.json()

        self.assertEqual(body["count"], 1)
        book = body["books"][0]
        self.assertEqual(book["title"], "Admin Book")
        self.assertEqual(book["stock_quantity"], 8)
        self.assertIn("description", book)
        self.assertIn("publisher", book)

    def test_catalogue_can_be_searched_and_filtered(self):
        Book.objects.create(
            **book_data(
                title="Deep Learning",
                author="Ian Goodfellow",
                isbn="9780201633610",
                category="Science",
                stock_quantity=0,
            )
        )

        search = self.admin_client.get(
            reverse("admin_book_collection"), {"q": "goodfellow"}
        ).json()
        self.assertEqual(search["count"], 1)
        self.assertEqual(search["books"][0]["title"], "Deep Learning")

        category = self.admin_client.get(
            reverse("admin_book_collection"), {"category": "Science"}
        ).json()
        self.assertEqual(category["count"], 1)

        low_stock = self.admin_client.get(
            reverse("admin_book_collection"), {"low_stock": 0}
        ).json()
        self.assertEqual(low_stock["count"], 1)
        self.assertEqual(low_stock["books"][0]["stock_quantity"], 0)

    def test_invalid_low_stock_filter_is_rejected(self):
        response = self.admin_client.get(
            reverse("admin_book_collection"), {"low_stock": "many"}
        )

        self.assertEqual(response.status_code, 400)

    def test_administrator_can_add_a_book(self):
        response = self.post_json(
            self.admin_client,
            reverse("admin_book_collection"),
            {
                "title": "The Pragmatic Programmer",
                "author": "Andrew Hunt",
                "isbn": "978-0201616224",
                "description": "Tips for the pragmatic developer.",
                "category": "Software Engineering",
                "price": "44.95",
                "stock_quantity": 6,
                "publisher": "Addison-Wesley",
                "publication_date": "1999-10-20",
                "cover_image_url": "",
            },
        )

        self.assertEqual(response.status_code, 201)
        book = response.json()["book"]

        self.assertEqual(book["title"], "The Pragmatic Programmer")
        # The ISBN is normalized by the model before it is stored.
        self.assertEqual(book["isbn"], "9780201616224")
        self.assertEqual(book["price"], "44.95")

        stored = Book.objects.get(pk=book["id"])
        self.assertEqual(stored.stock_quantity, 6)
        self.assertEqual(stored.publisher, "Addison-Wesley")

    def test_new_book_is_validated(self):
        response = self.post_json(
            self.admin_client,
            reverse("admin_book_collection"),
            {
                "title": "",
                "author": "",
                "isbn": "not-an-isbn",
                "category": "Fiction",
                "price": "-5.00",
                "stock_quantity": 1,
            },
        )

        self.assertEqual(response.status_code, 400)
        errors = response.json()["errors"]

        self.assertIn("title", errors)
        self.assertIn("author", errors)
        self.assertIn("isbn", errors)
        self.assertIn("price", errors)
        self.assertEqual(Book.objects.count(), 1)

    def test_duplicate_isbn_is_rejected(self):
        response = self.post_json(
            self.admin_client,
            reverse("admin_book_collection"),
            book_data(title="Copy", price="10.00"),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("isbn", response.json()["errors"])
        self.assertEqual(Book.objects.count(), 1)

    def test_administrator_can_update_stock_and_price(self):
        response = self.patch_json(
            self.admin_client,
            reverse("admin_book_detail", args=[self.book.pk]),
            {"stock_quantity": 25, "price": "19.99"},
        )

        self.assertEqual(response.status_code, 200)
        book = response.json()["book"]

        self.assertEqual(book["stock_quantity"], 25)
        self.assertEqual(book["price"], "19.99")

        self.book.refresh_from_db()
        self.assertEqual(self.book.stock_quantity, 25)
        self.assertEqual(self.book.price, Decimal("19.99"))

    def test_partial_update_keeps_untouched_fields(self):
        self.patch_json(
            self.admin_client,
            reverse("admin_book_detail", args=[self.book.pk]),
            {"stock_quantity": 3},
        )

        self.book.refresh_from_db()
        self.assertEqual(self.book.stock_quantity, 3)
        self.assertEqual(self.book.title, "Admin Book")
        self.assertEqual(self.book.price, Decimal("30.00"))

    def test_update_is_validated(self):
        response = self.patch_json(
            self.admin_client,
            reverse("admin_book_detail", args=[self.book.pk]),
            {"price": "-1.00"},
        )

        self.assertEqual(response.status_code, 400)
        self.book.refresh_from_db()
        self.assertEqual(self.book.price, Decimal("30.00"))

    def test_administrator_can_delete_an_unordered_book(self):
        response = self.admin_client.delete(
            reverse("admin_book_detail", args=[self.book.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])
        self.assertFalse(Book.objects.filter(pk=self.book.pk).exists())

    def test_book_on_an_existing_order_cannot_be_deleted(self):
        order = Order.objects.create(
            session_key="orderedsession",
            status=Order.STATUS_CONFIRMED,
            total_amount=Decimal("30.00"),
        )
        OrderItem.objects.create(
            order=order,
            book=self.book,
            book_title=self.book.title,
            unit_price=self.book.price,
            quantity=1,
        )

        response = self.admin_client.delete(
            reverse("admin_book_detail", args=[self.book.pk])
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("existing orders", response.json()["error"])
        self.assertTrue(Book.objects.filter(pk=self.book.pk).exists())

    def test_unknown_book_returns_404(self):
        response = self.admin_client.get(
            reverse("admin_book_detail", args=[999999])
        )

        self.assertEqual(response.status_code, 404)


class AdminOrderManagementTests(AdminTestCase):
    """OBS-F-018: administrators manage order information."""

    def setUp(self):
        super().setUp()
        self.book = Book.objects.create(**book_data())
        self.order = Order.objects.create(
            user=self.customer,
            session_key="ordersession",
            status=Order.STATUS_CONFIRMED,
            total_amount=Decimal("60.00"),
            paid_at=timezone.now(),
            stock_reserved=True,
        )
        OrderItem.objects.create(
            order=self.order,
            book=self.book,
            book_title=self.book.title,
            unit_price=Decimal("30.00"),
            quantity=2,
        )

    def set_status(self, status, order=None):
        return self.post_json(
            self.admin_client,
            reverse("admin_order_status", args=[(order or self.order).pk]),
            {"status": status},
        )

    def test_order_list_shows_every_customers_orders(self):
        Order.objects.create(
            session_key="guestsession",
            total_amount=Decimal("5.00"),
        )

        response = self.admin_client.get(reverse("admin_order_collection"))

        self.assertEqual(response.status_code, 200)
        body = response.json()

        self.assertEqual(body["count"], 2)
        self.assertEqual(len(body["orders"]), 2)
        self.assertIn("allowed_transitions", body)

        owned = next(
            order for order in body["orders"] if order["id"] == self.order.pk
        )
        self.assertEqual(owned["customer"]["username"], "shopper")

    def test_order_list_can_be_filtered_by_status(self):
        Order.objects.create(
            session_key="pendingsession",
            total_amount=Decimal("5.00"),
        )

        body = self.admin_client.get(
            reverse("admin_order_collection"), {"status": "pending"}
        ).json()

        self.assertEqual(body["count"], 1)
        self.assertEqual(body["orders"][0]["status"], "PENDING")

    def test_invalid_status_filter_is_rejected(self):
        response = self.admin_client.get(
            reverse("admin_order_collection"), {"status": "LOST"}
        )

        self.assertEqual(response.status_code, 400)

    def test_order_list_can_be_searched_by_customer(self):
        body = self.admin_client.get(
            reverse("admin_order_collection"), {"q": "shopper"}
        ).json()

        self.assertEqual(body["count"], 1)
        self.assertEqual(body["orders"][0]["id"], self.order.pk)

    def test_order_list_is_paginated(self):
        for index in range(3):
            Order.objects.create(
                session_key=f"bulk{index}",
                total_amount=Decimal("1.00"),
            )

        body = self.admin_client.get(
            reverse("admin_order_collection"), {"limit": 2, "offset": 1}
        ).json()

        self.assertEqual(body["count"], 4)
        self.assertEqual(body["limit"], 2)
        self.assertEqual(body["offset"], 1)
        self.assertEqual(len(body["orders"]), 2)

    def test_invalid_pagination_is_rejected(self):
        self.assertEqual(
            self.admin_client.get(
                reverse("admin_order_collection"), {"limit": "lots"}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.admin_client.get(
                reverse("admin_order_collection"), {"offset": "later"}
            ).status_code,
            400,
        )

    def test_order_detail_includes_items_customer_and_payments(self):
        Payment.objects.create(
            order=self.order,
            amount=Decimal("60.00"),
            status=Payment.STATUS_SUCCEEDED,
            reference="MOCK-REF",
            card_last4="4242",
            user=self.customer,
        )

        response = self.admin_client.get(
            reverse("admin_order_detail", args=[self.order.pk])
        )

        self.assertEqual(response.status_code, 200)
        order = response.json()["order"]

        self.assertEqual(order["customer"]["email"], "shopper@example.com")
        self.assertEqual(order["session_key"], "ordersession")
        self.assertEqual(len(order["items"]), 1)
        self.assertEqual(len(order["payments"]), 1)
        self.assertEqual(order["payments"][0]["status"], "SUCCEEDED")

    def test_administrator_advances_the_order_through_fulfilment(self):
        for status in ("PROCESSING", "SHIPPED", "DELIVERED"):
            with self.subTest(status=status):
                response = self.set_status(status)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["order"]["status"], status)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_DELIVERED)

    def test_fulfilment_steps_cannot_be_skipped(self):
        response = self.set_status("DELIVERED")

        self.assertEqual(response.status_code, 409)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_CONFIRMED)

    def test_unpaid_order_cannot_be_advanced(self):
        pending = Order.objects.create(
            session_key="pendingsession",
            total_amount=Decimal("5.00"),
        )

        response = self.set_status("PROCESSING", order=pending)

        self.assertEqual(response.status_code, 409)
        pending.refresh_from_db()
        self.assertEqual(pending.status, Order.STATUS_PENDING)

    def test_status_cannot_move_backwards(self):
        self.assertEqual(self.set_status("PROCESSING").status_code, 200)

        response = self.set_status("CONFIRMED")

        self.assertEqual(response.status_code, 409)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_PROCESSING)

    def test_unknown_status_is_rejected(self):
        response = self.set_status("TELEPORTED")

        self.assertEqual(response.status_code, 409)
        self.assertIn("not a valid order status", response.json()["error"])

    def test_status_is_required(self):
        response = self.post_json(
            self.admin_client,
            reverse("admin_order_status", args=[self.order.pk]),
            {},
        )

        self.assertEqual(response.status_code, 400)

    def test_cancellation_through_the_status_endpoint_is_refused(self):
        response = self.set_status("CANCELLED")

        self.assertEqual(response.status_code, 409)
        self.assertIn("cancellation operation", response.json()["error"])
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_CONFIRMED)

    def test_administrator_cancellation_releases_stock(self):
        self.book.stock_quantity = 6
        self.book.save(update_fields=["stock_quantity"])

        response = self.post_json(
            self.admin_client,
            reverse("admin_order_cancel", args=[self.order.pk]),
            {"reason": "Customer called to cancel"},
        )

        self.assertEqual(response.status_code, 200)
        order = response.json()["order"]

        self.assertEqual(order["status"], "CANCELLED")
        self.assertEqual(
            order["cancellation_reason"], "Customer called to cancel"
        )
        self.assertTrue(order["refund_due"])

        self.book.refresh_from_db()
        self.assertEqual(self.book.stock_quantity, 8)

    def test_administrator_cancellation_records_a_default_reason(self):
        body = self.post_json(
            self.admin_client,
            reverse("admin_order_cancel", args=[self.order.pk]),
            {},
        ).json()

        self.assertEqual(
            body["order"]["cancellation_reason"],
            "Cancelled by an administrator.",
        )

    def test_shipped_order_cannot_be_cancelled_by_an_administrator(self):
        self.order.status = Order.STATUS_SHIPPED
        self.order.save(update_fields=["status"])

        response = self.post_json(
            self.admin_client,
            reverse("admin_order_cancel", args=[self.order.pk]),
            {},
        )

        self.assertEqual(response.status_code, 409)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_SHIPPED)

    def test_unknown_order_returns_404(self):
        self.assertEqual(
            self.set_status("PROCESSING", order=Order(pk=999999)).status_code,
            404,
        )


class AdminCustomerManagementTests(AdminTestCase):
    """Issue #24: administrator customer management."""

    def setUp(self):
        super().setUp()
        self.paid_order = Order.objects.create(
            user=self.customer,
            session_key="customersession",
            status=Order.STATUS_DELIVERED,
            total_amount=Decimal("40.00"),
            paid_at=timezone.now(),
        )
        Order.objects.create(
            user=self.customer,
            session_key="customersession",
            status=Order.STATUS_CANCELLED,
            total_amount=Decimal("15.00"),
            cancelled_at=timezone.now(),
        )
        Order.objects.create(
            user=self.customer,
            session_key="customersession",
            status=Order.STATUS_PENDING,
            total_amount=Decimal("99.00"),
        )

    def customers(self, params=None):
        response = self.admin_client.get(
            reverse("admin_customer_collection"), params or {}
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_customer_list_reports_order_aggregates(self):
        body = self.customers()

        shopper = next(
            row for row in body["customers"] if row["username"] == "shopper"
        )

        self.assertEqual(shopper["email"], "shopper@example.com")
        self.assertTrue(shopper["is_active"])
        self.assertEqual(shopper["order_count"], 3)
        self.assertEqual(shopper["cancelled_order_count"], 1)
        # Only revenue-bearing orders count towards the amount spent, so
        # the pending and cancelled orders are excluded.
        self.assertEqual(shopper["total_spent"], "40.00")
        self.assertTrue(shopper["last_order_at"])

    def test_customer_without_orders_reports_zero(self):
        body = self.customers()

        admin_row = next(
            row for row in body["customers"] if row["username"] == "bookadmin"
        )

        self.assertEqual(admin_row["order_count"], 0)
        self.assertEqual(admin_row["total_spent"], "0.00")
        self.assertIsNone(admin_row["last_order_at"])

    def test_customer_list_can_be_searched(self):
        body = self.customers({"q": "shopper@example"})

        self.assertEqual(body["count"], 1)
        self.assertEqual(body["customers"][0]["username"], "shopper")

    def test_customer_list_can_be_filtered_by_status(self):
        self.customer.is_active = False
        self.customer.save(update_fields=["is_active"])

        active = self.customers({"status": "active"})
        self.assertTrue(
            all(row["is_active"] for row in active["customers"])
        )

        inactive = self.customers({"status": "inactive"})
        self.assertEqual(inactive["count"], 1)
        self.assertEqual(inactive["customers"][0]["username"], "shopper")

    def test_invalid_status_filter_is_rejected(self):
        response = self.admin_client.get(
            reverse("admin_customer_collection"), {"status": "banned"}
        )

        self.assertEqual(response.status_code, 400)

    def test_customer_detail_includes_their_orders(self):
        response = self.admin_client.get(
            reverse("admin_customer_detail", args=[self.customer.pk])
        )

        self.assertEqual(response.status_code, 200)
        customer = response.json()["customer"]

        self.assertEqual(customer["username"], "shopper")
        self.assertEqual(len(customer["orders"]), 3)
        self.assertEqual(customer["order_count"], 3)

    def test_unknown_customer_returns_404(self):
        response = self.admin_client.get(
            reverse("admin_customer_detail", args=[999999])
        )

        self.assertEqual(response.status_code, 404)

    def test_administrator_can_deactivate_a_customer(self):
        response = self.post_json(
            self.admin_client,
            reverse("admin_customer_status", args=[self.customer.pk]),
            {"is_active": False},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["customer"]["is_active"])

        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_active)

        # A deactivated customer can no longer sign in, while their order
        # history is preserved.
        login = Client().post(
            reverse("api_login"),
            data=json.dumps(
                {"username": "shopper", "password": "ShopperPass123"}
            ),
            content_type="application/json",
        )
        self.assertEqual(login.status_code, 401)
        self.assertEqual(
            Order.objects.filter(user=self.customer).count(), 3
        )

    def test_administrator_can_reactivate_a_customer(self):
        self.customer.is_active = False
        self.customer.save(update_fields=["is_active"])

        response = self.post_json(
            self.admin_client,
            reverse("admin_customer_status", args=[self.customer.pk]),
            {"is_active": True},
        )

        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_active)

    def test_is_active_must_be_a_boolean(self):
        response = self.post_json(
            self.admin_client,
            reverse("admin_customer_status", args=[self.customer.pk]),
            {"is_active": "no"},
        )

        self.assertEqual(response.status_code, 400)

    def test_administrator_cannot_deactivate_themselves(self):
        response = self.post_json(
            self.admin_client,
            reverse("admin_customer_status", args=[self.admin.pk]),
            {"is_active": False},
        )

        self.assertEqual(response.status_code, 400)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_other_administrators_cannot_be_deactivated(self):
        another_admin = get_user_model().objects.create_user(
            username="secondadmin",
            email="second@example.com",
            password="SecondPass123",
            is_staff=True,
        )

        response = self.post_json(
            self.admin_client,
            reverse("admin_customer_status", args=[another_admin.pk]),
            {"is_active": False},
        )

        self.assertEqual(response.status_code, 403)
        another_admin.refresh_from_db()
        self.assertTrue(another_admin.is_active)


class AdminSalesReportTests(AdminTestCase):
    """Issue #24: administrators generate sales reports."""

    def setUp(self):
        super().setUp()
        self.book = Book.objects.create(**book_data())
        self.other_book = Book.objects.create(
            **book_data(
                title="Second Admin Book",
                isbn="9780201633610",
                price=Decimal("10.00"),
            )
        )

        self.delivered = self._order(
            Order.STATUS_DELIVERED, Decimal("60.00"), paid=True
        )
        self._item(self.delivered, self.book, Decimal("30.00"), 2)

        self.confirmed = self._order(
            Order.STATUS_CONFIRMED, Decimal("30.00"), paid=True
        )
        self._item(self.confirmed, self.other_book, Decimal("10.00"), 3)

        # Neither of these counts as revenue.
        self.pending = self._order(Order.STATUS_PENDING, Decimal("99.00"))
        self._item(self.pending, self.book, Decimal("30.00"), 3)

        self.cancelled = self._order(
            Order.STATUS_CANCELLED, Decimal("45.00"), paid=True
        )
        self._item(self.cancelled, self.book, Decimal("30.00"), 1)

    def _order(self, status, total, paid=False):
        return Order.objects.create(
            user=self.customer,
            session_key="reportsession",
            status=status,
            total_amount=total,
            paid_at=timezone.now() if paid else None,
        )

    def _item(self, order, book, unit_price, quantity):
        return OrderItem.objects.create(
            order=order,
            book=book,
            book_title=book.title,
            unit_price=unit_price,
            quantity=quantity,
        )

    def report(self, params=None):
        response = self.admin_client.get(
            reverse("admin_sales_report"), params or {}
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["report"]

    def test_report_counts_only_revenue_bearing_orders(self):
        revenue = self.report()["revenue"]

        self.assertEqual(revenue["total"], "90.00")
        self.assertEqual(revenue["order_count"], 2)
        self.assertEqual(revenue["average_order_value"], "45.00")
        self.assertEqual(revenue["items_sold"], 5)
        self.assertIn("CONFIRMED", revenue["counted_statuses"])
        self.assertNotIn("PENDING", revenue["counted_statuses"])
        self.assertNotIn("CANCELLED", revenue["counted_statuses"])

    def test_report_breaks_orders_down_by_status(self):
        statuses = self.report()["orders_by_status"]

        self.assertEqual(statuses["DELIVERED"], 1)
        self.assertEqual(statuses["CONFIRMED"], 1)
        self.assertEqual(statuses["PENDING"], 1)
        self.assertEqual(statuses["CANCELLED"], 1)
        self.assertEqual(statuses["SHIPPED"], 0)

    def test_report_lists_best_selling_books(self):
        top_books = self.report()["top_books"]

        self.assertEqual(len(top_books), 2)

        best = top_books[0]
        self.assertEqual(best["title"], "Second Admin Book")
        self.assertEqual(best["quantity_sold"], 3)
        self.assertEqual(best["revenue"], "30.00")

        second = top_books[1]
        self.assertEqual(second["title"], "Admin Book")
        self.assertEqual(second["quantity_sold"], 2)
        self.assertEqual(second["revenue"], "60.00")

    def test_report_includes_a_daily_breakdown(self):
        daily = self.report()["daily"]

        self.assertEqual(len(daily), 1)
        self.assertEqual(daily[0]["order_count"], 2)
        self.assertEqual(daily[0]["revenue"], "90.00")

    def test_report_period_can_be_restricted(self):
        today = timezone.localdate()
        tomorrow = today + timezone.timedelta(days=1)

        inside = self.report(
            {"start": today.isoformat(), "end": today.isoformat()}
        )
        self.assertEqual(inside["revenue"]["order_count"], 2)
        self.assertEqual(inside["period"]["start"], today.isoformat())

        outside = self.report(
            {
                "start": tomorrow.isoformat(),
                "end": (tomorrow + timezone.timedelta(days=5)).isoformat(),
            }
        )
        self.assertEqual(outside["revenue"]["order_count"], 0)
        self.assertEqual(outside["revenue"]["total"], "0.00")
        self.assertEqual(outside["top_books"], [])

    def test_invalid_period_is_rejected(self):
        self.assertEqual(
            self.admin_client.get(
                reverse("admin_sales_report"), {"start": "yesterday"}
            ).status_code,
            400,
        )

        response = self.admin_client.get(
            reverse("admin_sales_report"),
            {"start": "2026-02-01", "end": "2026-01-01"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("later than", response.json()["error"])

    def test_empty_period_reports_zeroes(self):
        Order.objects.all().delete()

        report = self.report()

        self.assertEqual(report["revenue"]["total"], "0.00")
        self.assertEqual(report["revenue"]["order_count"], 0)
        self.assertEqual(report["revenue"]["average_order_value"], "0.00")
        self.assertEqual(report["revenue"]["items_sold"], 0)
        self.assertEqual(report["daily"], [])

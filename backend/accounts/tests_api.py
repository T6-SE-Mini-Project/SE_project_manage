
"""Tests for the JSON authentication API used by the React frontend.

The session endpoints are the enabler for order history (issue #10),
reviews (issue #11) and the administrator screens (issues #12 and #24),
so they are covered here alongside the guest-to-customer handover of the
cart and of guest orders.
"""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from books.models import Book
from cart.models import Cart
from orders.models import Order


class AuthApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="apicustomer",
            email="api@example.com",
            password="ApiPassword123",
        )

    def post(self, name, payload):
        return self.client.post(
            reverse(name),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_session_reports_anonymous_caller(self):
        response = self.client.get(reverse("api_session_detail"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"authenticated": False, "user": None},
        )

    def test_login_starts_a_session(self):
        response = self.post(
            "api_login",
            {"username": "apicustomer", "password": "ApiPassword123"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()

        self.assertTrue(body["authenticated"])
        self.assertEqual(body["user"]["username"], "apicustomer")
        self.assertEqual(body["user"]["email"], "api@example.com")
        self.assertFalse(body["user"]["is_staff"])

        session = self.client.get(reverse("api_session_detail")).json()
        self.assertTrue(session["authenticated"])

    def test_login_with_a_wrong_password_is_rejected(self):
        response = self.post(
            "api_login",
            {"username": "apicustomer", "password": "WrongPassword"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.json())

        session = self.client.get(reverse("api_session_detail")).json()
        self.assertFalse(session["authenticated"])

    def test_login_requires_both_fields(self):
        response = self.post("api_login", {"username": "apicustomer"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("required", response.json()["error"])

    def test_inactive_account_cannot_log_in(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.post(
            "api_login",
            {"username": "apicustomer", "password": "ApiPassword123"},
        )

        self.assertEqual(response.status_code, 401)

    def test_logout_ends_the_session(self):
        self.post(
            "api_login",
            {"username": "apicustomer", "password": "ApiPassword123"},
        )

        response = self.post("api_logout", {})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["authenticated"])
        self.assertFalse(
            self.client.get(reverse("api_session_detail")).json()[
                "authenticated"
            ]
        )

    def test_registration_creates_customer_without_signing_them_in(self):
        response = self.post(
            "api_register",
            {
                "username": "newcustomer",
                "email": "new@example.com",
                "password1": "BrandNewPass123",
                "password2": "BrandNewPass123",
            },
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()

        self.assertFalse(body["authenticated"])
        self.assertIsNone(body["user"])

        created = get_user_model().objects.get(username="newcustomer")
        self.assertEqual(created.email, "new@example.com")

        # The password must be stored hashed, never in clear text.
        self.assertNotEqual(created.password, "BrandNewPass123")
        self.assertTrue(created.check_password("BrandNewPass123"))

        # Registration must leave the customer logged out.
        session = self.client.get(reverse("api_session_detail"))
        self.assertEqual(
            session.json(),
            {"authenticated": False, "user": None},
        )

    def test_registration_reports_field_errors(self):
        response = self.post(
            "api_register",
            {
                "username": "apicustomer",
                "email": "another@example.com",
                "password1": "BrandNewPass123",
                "password2": "DifferentPass123",
            },
        )

        self.assertEqual(response.status_code, 400)
        body = response.json()

        self.assertIn("error", body)
        self.assertIn("errors", body)
        self.assertTrue(set(body["errors"]) & {"username", "password2"})

    def test_registration_rejects_a_duplicate_email(self):
        response = self.post(
            "api_register",
            {
                "username": "anothercustomer",
                "email": "api@example.com",
                "password1": "BrandNewPass123",
                "password2": "BrandNewPass123",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json()["errors"])

    def test_unsupported_methods_are_rejected(self):
        self.assertEqual(
            self.client.get(reverse("api_login")).status_code, 405
        )
        self.assertEqual(
            self.client.post(reverse("api_session_detail")).status_code, 405
        )


class GuestHandoverTests(TestCase):
    """Logging in must not lose the guest cart or guest orders."""

    def setUp(self):
        self.book = Book.objects.create(
            title="Handover Book",
            author="Handover Author",
            isbn="9780132350884",
            category="Fiction",
            price=Decimal("10.00"),
            stock_quantity=5,
        )
        self.user = get_user_model().objects.create_user(
            username="handover",
            email="handover@example.com",
            password="HandoverPass123",
        )

    def login(self):
        return self.client.post(
            reverse("api_login"),
            data=json.dumps(
                {"username": "handover", "password": "HandoverPass123"}
            ),
            content_type="application/json",
        )

    def add_to_cart(self, quantity=1):
        response = self.client.post(
            reverse("cart_item_add"),
            data=json.dumps(
                {"book_id": self.book.pk, "quantity": quantity}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_guest_cart_survives_login(self):
        self.add_to_cart(quantity=2)

        self.assertEqual(self.login().status_code, 200)

        cart = self.client.get(reverse("cart_detail")).json()["cart"]

        self.assertEqual(cart["item_count"], 2)
        self.assertEqual(cart["total"], "20.00")

        # The cart is now owned by the signed-in customer.
        carts = Cart.objects.filter(user=self.user)
        self.assertEqual(carts.count(), 1)

    
    def test_guest_cart_survives_registration(self):
        self.add_to_cart(quantity=3)

        response = self.client.post(
            reverse("api_register"),
            data=json.dumps(
                {
                    "username": "freshcustomer",
                    "email": "fresh@example.com",
                    "password1": "FreshPass12345",
                    "password2": "FreshPass12345",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["authenticated"])

        # Registration preserves the guest cart and session.
        cart = self.client.get(reverse("cart_detail")).json()["cart"]
        self.assertEqual(cart["item_count"], 3)

        # The customer must explicitly log in before claiming the cart.
        login_response = self.client.post(
            reverse("api_login"),
            data=json.dumps(
                {
                    "username": "freshcustomer",
                    "password": "FreshPass12345",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(login_response.status_code, 200)
        self.assertTrue(login_response.json()["authenticated"])

        cart = self.client.get(reverse("cart_detail")).json()["cart"]
        self.assertEqual(cart["item_count"], 3)

        # After login, the cart should belong to the new customer.
        created_user = get_user_model().objects.get(
            username="freshcustomer"
        )
        self.assertTrue(
            Cart.objects.filter(user=created_user).exists()
        )

    def test_guest_order_is_claimed_by_the_account(self):
        self.add_to_cart(quantity=1)
        placed = self.client.post(reverse("order_collection"))
        self.assertEqual(placed.status_code, 201)
        order_id = placed.json()["order"]["id"]

        self.assertEqual(self.login().status_code, 200)

        self.assertEqual(
            Order.objects.get(pk=order_id).user_id,
            self.user.pk,
        )

    def test_login_does_not_claim_another_customers_order(self):
        other_user = get_user_model().objects.create_user(
            username="owner",
            email="owner@example.com",
            password="OwnerPass123",
        )
        order = Order.objects.create(
            user=other_user,
            session_key="someonelsesession",
            total_amount=Decimal("10.00"),
        )

        self.assertEqual(self.login().status_code, 200)

        order.refresh_from_db()
        self.assertEqual(order.user_id, other_user.pk)

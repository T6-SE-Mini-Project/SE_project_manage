
"""Tests for the JSON authentication API used by the React frontend.

Identity arrives as a Firebase ID token in the Authorization header, so
every request here carries one minted by ``FirebaseTokenMixin``. The
session endpoints are the enabler for order history (issue #10), reviews
(issue #11) and the administrator screens (issues #12 and #24), so they
are covered here alongside the guest-to-customer handover of the cart and
of guest orders.
"""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from books.models import Book
from cart.models import Cart
from orders.models import Order

from .middleware import SESSION_UID_KEY
from .models import PROVIDER_GOOGLE, FirebaseIdentity
from .tests_firebase import FirebaseTokenMixin


class AuthApiTests(FirebaseTokenMixin, TestCase):
    def get(self, name, token=None, **extra):
        return self.client.get(reverse(name), **self.auth(token), **extra)

    def post(self, name, token=None, payload=None, **extra):
        return self.client.post(
            reverse(name),
            data=json.dumps(payload if payload is not None else {}),
            content_type="application/json",
            **self.auth(token),
            **extra,
        )

    def auth(self, token):
        """Request kwargs carrying a bearer token, or none at all."""
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}

    def test_session_reports_anonymous_caller(self):
        response = self.get("api_session_detail")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"authenticated": False, "user": None},
        )

    def test_session_reports_the_customer_a_token_identifies(self):
        response = self.get(
            "api_session_detail",
            self.make_token(uid="uid-session", email="api@example.com"),
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()

        self.assertTrue(body["authenticated"])
        self.assertEqual(body["user"]["email"], "api@example.com")
        self.assertEqual(body["user"]["uid"], "uid-session")
        self.assertFalse(body["user"]["is_staff"])

    def test_signing_in_creates_the_account_and_records_the_uid(self):
        response = self.post(
            "api_signin",
            self.make_token(uid="uid-signin", email="new@example.com"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["authenticated"])
        self.assertEqual(response.json()["user"]["uid"], "uid-signin")

        identity = FirebaseIdentity.objects.get(uid="uid-signin")
        self.assertEqual(identity.user.email, "new@example.com")
        self.assertIsNotNone(identity.last_login_at)
        self.assertIsNotNone(identity.user.last_login)

    def test_google_sign_in_is_accepted_and_recorded(self):
        response = self.post(
            "api_signin",
            self.make_token(
                uid="uid-google",
                email="google@example.com",
                provider=PROVIDER_GOOGLE,
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["provider"], PROVIDER_GOOGLE)

    def test_signing_in_without_a_token_is_rejected(self):
        response = self.post("api_signin")

        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.json())
        self.assertEqual(FirebaseIdentity.objects.count(), 0)

    def test_an_invalid_token_is_rejected_with_401(self):
        response = self.get("api_session_detail", "not.a.token")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "invalid_token")

    def test_an_expired_token_is_rejected_with_401(self):
        response = self.get(
            "api_session_detail", self.make_token(expires_in=-60)
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn("expired", response.json()["error"].lower())

    def test_a_token_for_another_project_is_rejected(self):
        response = self.get(
            "api_session_detail",
            self.make_token(audience="another-firebase-project"),
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(FirebaseIdentity.objects.count(), 0)

    def test_a_disabled_account_is_refused_with_403(self):
        # Administrators deactivate customers (issue #24). Firebase keeps
        # issuing them tokens, so the refusal has to happen here.
        token = self.make_token(uid="uid-disabled")
        self.assertEqual(self.post("api_signin", token).status_code, 200)

        user = FirebaseIdentity.objects.get(uid="uid-disabled").user
        user.is_active = False
        user.save(update_fields=["is_active"])

        response = self.get("api_session_detail", token)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "account_disabled")

    def test_the_token_authenticates_protected_endpoints(self):
        # No session is established anywhere; the order history is reached
        # on the strength of the token alone.
        response = self.get("order_collection", self.make_token(uid="uid-orders"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)

    def test_protected_endpoints_still_refuse_anonymous_callers(self):
        self.assertEqual(self.get("admin_book_collection").status_code, 401)

    def test_logout_forgets_the_session(self):
        token = self.make_token(uid="uid-logout")
        self.assertEqual(self.post("api_signin", token).status_code, 200)

        response = self.post("api_logout", token)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"authenticated": False, "user": None}
        )
        self.assertNotIn(SESSION_UID_KEY, self.client.session)

    def test_a_dropped_token_leaves_the_caller_anonymous(self):
        # Signing out in the browser stops the SDK sending a token, which
        # is what ends the authenticated state.
        token = self.make_token(uid="uid-dropped")
        self.post("api_signin", token)

        self.assertFalse(
            self.get("api_session_detail").json()["authenticated"]
        )

    def test_unsupported_methods_are_rejected(self):
        self.assertEqual(
            self.client.get(reverse("api_signin")).status_code, 405
        )
        self.assertEqual(
            self.client.post(reverse("api_session_detail")).status_code, 405
        )


class GuestHandoverTests(FirebaseTokenMixin, TestCase):
    """Signing in must not lose the guest cart or guest orders."""

    def setUp(self):
        super().setUp()

        self.book = Book.objects.create(
            title="Handover Book",
            author="Handover Author",
            isbn="9780132350884",
            category="Fiction",
            price=Decimal("10.00"),
            stock_quantity=5,
        )
        self.token = self.make_token(
            uid="uid-handover", email="handover@example.com"
        )

    def sign_in(self, token=None):
        return self.client.post(
            reverse("api_signin"),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token or self.token}",
        )

    def add_to_cart(self, quantity=1):
        response = self.client.post(
            reverse("cart_item_add"),
            data=json.dumps({"book_id": self.book.pk, "quantity": quantity}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def cart(self, token=None):
        response = self.client.get(
            reverse("cart_detail"),
            **({"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}),
        )
        return response.json()["cart"]

    def test_guest_cart_survives_sign_in(self):
        self.add_to_cart(quantity=2)

        self.assertEqual(self.sign_in().status_code, 200)

        cart = self.cart(self.token)

        self.assertEqual(cart["item_count"], 2)
        self.assertEqual(cart["total"], "20.00")

        # The cart is now owned by the signed-in customer.
        user = FirebaseIdentity.objects.get(uid="uid-handover").user
        self.assertEqual(Cart.objects.filter(user=user).count(), 1)

    def test_sign_in_cycles_the_session_key(self):
        self.add_to_cart()
        before = self.client.session.session_key

        self.sign_in()

        self.assertNotEqual(self.client.session.session_key, before)
        self.assertEqual(
            self.client.session[SESSION_UID_KEY], "uid-handover"
        )

    def test_guest_order_is_claimed_by_the_account(self):
        self.add_to_cart(quantity=1)
        placed = self.client.post(reverse("order_collection"))
        self.assertEqual(placed.status_code, 201)
        order_id = placed.json()["order"]["id"]

        self.assertEqual(self.sign_in().status_code, 200)

        user = FirebaseIdentity.objects.get(uid="uid-handover").user
        self.assertEqual(Order.objects.get(pk=order_id).user_id, user.pk)

    def test_sign_in_does_not_claim_another_customers_order(self):
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

        self.assertEqual(self.sign_in().status_code, 200)

        order.refresh_from_db()
        self.assertEqual(order.user_id, other_user.pk)

    def test_a_second_customer_does_not_inherit_the_first_ones_cart(self):
        # The first customer signs in, fills a cart and closes the tab
        # without logging out; the session cookie is still in the browser.
        self.sign_in()
        self.add_to_cart(quantity=2)
        self.assertEqual(self.cart(self.token)["item_count"], 2)

        second_token = self.make_token(
            uid="uid-second", email="second@example.com"
        )
        self.assertEqual(self.sign_in(second_token).status_code, 200)

        self.assertEqual(self.cart(second_token)["item_count"], 0)

        # And the first customer's cart is untouched.
        first_user = FirebaseIdentity.objects.get(uid="uid-handover").user
        first_cart = Cart.objects.get(user=first_user)
        self.assertEqual(first_cart.item_count, 2)

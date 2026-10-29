"""Tests for the API rate limits (config/throttle.py).

The suite runs with throttling off (see ``config.settings_test``), because
tests share a process and one test's requests would otherwise count
against the next one's. These turn it on and clear the counters around
each test, so a limit is reached deliberately rather than by accident.
"""

import json
import types
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import caches
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from accounts.tests_firebase import FirebaseTokenMixin
from books.models import Book
from config import throttle

THROTTLED = {"THROTTLE_ENABLED": True}

#: A fixed point five seconds into a window. The window a request counts
#: against comes from the wall clock, so a test that spends its allowance
#: and expects the next request to be refused fails whenever a real minute
#: boundary falls between those requests — rarely, and never twice in the
#: same place. Freezing the clock makes "the fourth request is refused"
#: mean exactly that. Rollover is covered on its own, in
#: ``ThrottleResilienceTests``.
FROZEN_NOW = 1_767_225_605.0  # 2026-01-01T00:00:05Z


class ThrottleTestCase(TestCase):
    """Clears the counters and freezes the window around each test."""

    def setUp(self):
        super().setUp()
        caches[throttle.THROTTLE_CACHE].clear()
        self.addCleanup(caches[throttle.THROTTLE_CACHE].clear)

        # Only the module's own view of the clock, so the cache's expiry
        # and everything else still run on the real one.
        frozen = mock.patch.object(
            throttle, "time", types.SimpleNamespace(time=lambda: FROZEN_NOW)
        )
        frozen.start()
        self.addCleanup(frozen.stop)


@override_settings(**THROTTLED)
class ReadLimitTests(ThrottleTestCase):
    @override_settings(THROTTLE_READ_RATE=3)
    def test_a_caller_over_the_read_limit_is_refused(self):
        catalogue = reverse("book_list")

        for attempt in range(3):
            response = self.client.get(catalogue)
            self.assertEqual(response.status_code, 200, f"attempt {attempt}")

        refused = self.client.get(catalogue)

        self.assertEqual(refused.status_code, 429)
        self.assertEqual(refused.json()["code"], "rate_limited")

    @override_settings(THROTTLE_READ_RATE=2)
    def test_the_refusal_says_how_long_to_wait(self):
        self.client.get(reverse("book_list"))
        self.client.get(reverse("book_list"))

        refused = self.client.get(reverse("book_list"))

        self.assertEqual(refused.status_code, 429)
        # Retry-After is the only machine-readable part of a 429 that a
        # client or crawler is expected to obey.
        retry_after = int(refused["Retry-After"])
        self.assertGreater(retry_after, 0)
        self.assertLessEqual(retry_after, throttle.WINDOW_SECONDS)

    @override_settings(THROTTLE_READ_RATE=5)
    def test_the_remaining_allowance_is_reported(self):
        first = self.client.get(reverse("book_list"))
        second = self.client.get(reverse("book_list"))

        self.assertEqual(first["X-RateLimit-Limit"], "5")
        self.assertEqual(first["X-RateLimit-Remaining"], "4")
        self.assertEqual(second["X-RateLimit-Remaining"], "3")

    @override_settings(THROTTLE_READ_RATE=1)
    def test_the_health_check_is_never_refused(self):
        self.client.get(reverse("book_list"))
        self.client.get(reverse("book_list"))

        # A 429 here reads as "this instance is unhealthy" and gets the
        # service restarted, turning a flood into an outage.
        self.assertEqual(self.client.get("/healthz/").status_code, 200)

    @override_settings(THROTTLE_READ_RATE=1, THROTTLE_WRITE_RATE=5)
    def test_reads_and_writes_are_counted_separately(self):
        self.client.get(reverse("book_list"))
        self.assertEqual(self.client.get(reverse("book_list")).status_code, 429)

        # The read allowance is spent; a write has its own.
        response = self.client.post(
            reverse("cart_item_add"),
            data=json.dumps({"book_id": 999999}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)


@override_settings(**THROTTLED)
class WriteLimitTests(ThrottleTestCase):
    def setUp(self):
        super().setUp()
        self.book = Book.objects.create(
            title="Throttled Book",
            author="Throttle Author",
            isbn="9780132350884",
            category="Fiction",
            price=Decimal("10.00"),
            stock_quantity=50,
        )

    @override_settings(THROTTLE_WRITE_RATE=2)
    def test_a_caller_over_the_write_limit_is_refused(self):
        def add_to_cart():
            return self.client.post(
                reverse("cart_item_add"),
                data=json.dumps({"book_id": self.book.pk, "quantity": 1}),
                content_type="application/json",
            )

        self.assertEqual(add_to_cart().status_code, 200)
        self.assertEqual(add_to_cart().status_code, 200)

        self.assertEqual(add_to_cart().status_code, 429)


@override_settings(**THROTTLED)
class CallerIdentityTests(FirebaseTokenMixin, ThrottleTestCase):
    """One caller's flood must not refuse anybody else's requests."""

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()

    @override_settings(THROTTLE_READ_RATE=1)
    def test_two_signed_in_customers_have_their_own_allowance(self):
        first = self.make_token(uid="uid-busy", email="busy@example.com")
        second = self.make_token(uid="uid-quiet", email="quiet@example.com")
        catalogue = reverse("book_list")

        self.assertEqual(
            self.client.get(
                catalogue, HTTP_AUTHORIZATION=f"Bearer {first}"
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                catalogue, HTTP_AUTHORIZATION=f"Bearer {first}"
            ).status_code,
            429,
        )

        # Keyed by uid, so the second customer is unaffected — and would
        # not be even from the same address.
        self.assertEqual(
            self.client.get(
                catalogue, HTTP_AUTHORIZATION=f"Bearer {second}"
            ).status_code,
            200,
        )

    @override_settings(THROTTLE_READ_RATE=1)
    def test_a_signed_in_caller_is_not_limited_by_anonymous_traffic(self):
        token = self.make_token(uid="uid-signed-in", email="in@example.com")
        catalogue = reverse("book_list")

        self.client.get(catalogue)
        self.assertEqual(self.client.get(catalogue).status_code, 429)

        self.assertEqual(
            self.client.get(
                catalogue, HTTP_AUTHORIZATION=f"Bearer {token}"
            ).status_code,
            200,
        )

    def test_a_token_identifies_the_caller_by_uid(self):
        request = self.factory.get("/api/books/")
        request.firebase_identity = mock.Mock(uid="uid-abc")

        self.assertEqual(throttle.caller_key(request), "uid:uid-abc")

    def test_an_anonymous_caller_is_identified_by_address(self):
        request = self.factory.get("/api/books/", REMOTE_ADDR="203.0.113.7")
        request.firebase_identity = None

        self.assertEqual(throttle.caller_key(request), "ip:203.0.113.7")


class ClientAddressTests(TestCase):
    """Reading X-Forwarded-For safely (see TRUSTED_PROXY_COUNT)."""

    def setUp(self):
        self.factory = RequestFactory()

    def request(self, forwarded=None, remote_addr="10.0.0.1"):
        headers = {"REMOTE_ADDR": remote_addr}
        if forwarded is not None:
            headers["HTTP_X_FORWARDED_FOR"] = forwarded
        return self.factory.get("/api/books/", **headers)

    @override_settings(TRUSTED_PROXY_COUNT=0)
    def test_without_trusted_proxies_the_header_is_ignored(self):
        # Nothing is in front of the service, so the header can only have
        # come from the client and means nothing.
        request = self.request(forwarded="198.51.100.9")

        self.assertEqual(throttle.client_ip(request), "10.0.0.1")

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_one_proxy_uses_the_address_it_observed(self):
        request = self.request(forwarded="198.51.100.9")

        self.assertEqual(throttle.client_ip(request), "198.51.100.9")

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_a_client_cannot_spoof_its_address(self):
        # The client prepended a forgery; the proxy appended what it
        # actually saw. Counting from the right is what ignores the lie —
        # otherwise a caller could rotate addresses and never be limited.
        request = self.request(forwarded="1.1.1.1, 198.51.100.9")

        self.assertEqual(throttle.client_ip(request), "198.51.100.9")

    @override_settings(TRUSTED_PROXY_COUNT=2)
    def test_two_proxies_look_past_the_nearer_one(self):
        # The production chain: client -> Vercel -> Render. Trusting one
        # hop here would bucket every customer together under Vercel's
        # address.
        request = self.request(forwarded="203.0.113.7, 198.51.100.9")

        self.assertEqual(throttle.client_ip(request), "203.0.113.7")

    @override_settings(TRUSTED_PROXY_COUNT=2)
    def test_a_shorter_chain_than_configured_falls_back_to_the_socket(self):
        request = self.request(forwarded="203.0.113.7")

        self.assertEqual(throttle.client_ip(request), "10.0.0.1")

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_a_missing_header_falls_back_to_the_socket(self):
        self.assertEqual(throttle.client_ip(self.request()), "10.0.0.1")


@override_settings(**THROTTLED)
class EndpointLimitTests(FirebaseTokenMixin, ThrottleTestCase):
    """The attempt limits on sign-in, payment and reviews."""

    def setUp(self):
        super().setUp()
        self.book = Book.objects.create(
            title="Limited Book",
            author="Limit Author",
            isbn="9780201633610",
            category="Fiction",
            price=Decimal("10.00"),
            stock_quantity=50,
        )

    def sign_in(self, uid, email):
        token = self.make_token(uid=uid, email=email)
        return self.client.post(
            reverse("api_signin"),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    @override_settings(THROTTLE_WRITE_RATE=1000)
    def test_sign_up_flooding_from_one_address_is_limited(self):
        # The sign-in endpoint creates an account on first use, so it is
        # the one that would be abused to fill the customer table. Each
        # attempt arrives with a uid of its own, which is why this limit is
        # counted per address: a per-account limit would count nothing.
        for attempt in range(throttle.RATE_SIGNIN):
            response = self.sign_in(
                f"uid-flood-{attempt}", f"flood{attempt}@example.com"
            )
            self.assertEqual(response.status_code, 200, f"attempt {attempt}")

        refused = self.sign_in("uid-flood-last", "last@example.com")

        self.assertEqual(refused.status_code, 429)
        # A refused attempt creates no account.
        self.assertFalse(
            get_user_model().objects.filter(email="last@example.com").exists()
        )

    @override_settings(THROTTLE_READ_RATE=1000)
    def test_account_creation_is_limited_on_every_endpoint(self):
        # The limit lives where the account is created — in the
        # authentication middleware — not on the sign-in route, so it
        # cannot be sidestepped by pointing a flood of fresh tokens at
        # some other endpoint.
        catalogue = reverse("book_list")

        for attempt in range(throttle.RATE_SIGNIN):
            token = self.make_token(
                uid=f"uid-side-{attempt}", email=f"side{attempt}@example.com"
            )
            response = self.client.get(
                catalogue, HTTP_AUTHORIZATION=f"Bearer {token}"
            )
            self.assertEqual(response.status_code, 200, f"attempt {attempt}")

        token = self.make_token(uid="uid-side-last", email="sl@example.com")
        refused = self.client.get(
            catalogue, HTTP_AUTHORIZATION=f"Bearer {token}"
        )

        self.assertEqual(refused.status_code, 429)
        self.assertFalse(
            get_user_model().objects.filter(email="sl@example.com").exists()
        )

    @override_settings(THROTTLE_READ_RATE=1000)
    def test_an_existing_account_is_not_counted_as_a_new_one(self):
        # Only the creation of an account is limited this way, so an
        # established customer's ordinary traffic must not spend the
        # allowance a new sign-up needs.
        token = self.make_token(uid="uid-regular", email="reg@example.com")
        auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
        catalogue = reverse("book_list")

        for _ in range(throttle.RATE_SIGNIN + 5):
            self.assertEqual(
                self.client.get(catalogue, **auth).status_code, 200
            )

        # A genuinely new account can still be created afterwards.
        fresh = self.make_token(uid="uid-newcomer", email="new@example.com")
        self.assertEqual(
            self.client.get(
                catalogue, HTTP_AUTHORIZATION=f"Bearer {fresh}"
            ).status_code,
            200,
        )

    @override_settings(THROTTLE_WRITE_RATE=1000)
    def test_payment_attempts_are_limited_more_tightly_than_writes(self):
        token = self.make_token(uid="uid-payer", email="payer@example.com")
        auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        def attempt_payment():
            return self.client.post(
                reverse("payment_create"),
                data=json.dumps({"order_id": 999999}),
                content_type="application/json",
                **auth,
            )

        for attempt in range(throttle.RATE_PAYMENT):
            # 404: the order does not exist. A failed attempt still counts,
            # which is the point — card testing never gets a 200 either.
            self.assertEqual(attempt_payment().status_code, 404)

        self.assertEqual(attempt_payment().status_code, 429)

    @override_settings(THROTTLE_WRITE_RATE=1000)
    def test_review_submissions_are_limited(self):
        token = self.make_token(uid="uid-reviewer", email="rev@example.com")
        auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        def submit():
            return self.client.post(
                reverse("review_collection"),
                data=json.dumps({"book_id": self.book.pk, "rating": 5}),
                content_type="application/json",
                **auth,
            )

        # The first succeeds, the rest are refused as duplicates (409),
        # and every one of them counts against the limit.
        self.assertEqual(submit().status_code, 201)
        for _ in range(throttle.RATE_REVIEW - 1):
            self.assertEqual(submit().status_code, 409)

        self.assertEqual(submit().status_code, 429)


@override_settings(**THROTTLED)
class ThrottleResilienceTests(ThrottleTestCase):
    def test_an_unreachable_counter_store_allows_the_request(self):
        # A rate limiter that refuses requests because Redis is down turns
        # a cache outage into an API outage.
        store = caches[throttle.THROTTLE_CACHE]

        with mock.patch.object(store, "add", side_effect=OSError("no route")):
            with override_settings(THROTTLE_READ_RATE=0):
                response = self.client.get(reverse("book_list"))

        self.assertEqual(response.status_code, 200)

    def test_a_missing_counter_cache_allows_the_request(self):
        with override_settings(
            CACHES={
                "default": {
                    "BACKEND": "django.core.cache.backends.dummy.DummyCache",
                }
            },
            THROTTLE_READ_RATE=0,
        ):
            # No "throttle" alias configured at all.
            response = self.client.get(reverse("book_list"))

        self.assertEqual(response.status_code, 200)

    def test_a_rolled_over_window_starts_the_count_again(self):
        store = caches[throttle.THROTTLE_CACHE]

        with mock.patch.object(store, "incr", side_effect=ValueError("gone")):
            allowed, remaining, retry_after = throttle.consume(
                "read", "ip:203.0.113.7", limit=1
            )

        # The key expired between add() and incr(): this request is the
        # first of the new window, not one over the limit.
        self.assertTrue(allowed)


class ThrottleDisabledTests(TestCase):
    """Nothing is counted while THROTTLE_ENABLED is off."""

    def test_no_limit_headers_are_added(self):
        response = self.client.get(reverse("book_list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("X-RateLimit-Limit", response)

    def test_requests_are_never_refused(self):
        for _ in range(20):
            self.assertEqual(
                self.client.get(reverse("book_list")).status_code, 200
            )

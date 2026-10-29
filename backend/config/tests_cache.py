"""Tests for the API response cache (config/cache.py).

The suite as a whole runs with caching off (see ``config.settings_test``),
so these turn a local-memory cache on explicitly. Local memory and Redis
go through the same ``django.core.cache`` interface, so everything here —
keys, scopes, namespace invalidation, degradation on failure — is the
behaviour that runs against Upstash.

The proof that an answer came from the cache is deliberately indirect: a
row is changed through the ORM, which does *not* invalidate anything, and
the endpoint is then expected to return the stale value. Nothing but a
cache hit can produce that.
"""

import json
import os
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.tests_firebase import FirebaseTokenMixin
from books.models import Book
from config import cache as cache_module
from orders.models import Order

# Local memory by default, so the cache suite needs no server. Point
# OBS_TEST_REDIS_URL at a Redis instance to run these same tests through
# the production backend instead:
#
#     redis-server --port 6399 --save '' --daemonize yes
#     OBS_TEST_REDIS_URL=redis://127.0.0.1:6399/0 \
#         python manage.py test config.tests_cache --settings=config.settings_test
TEST_REDIS_URL = os.environ.get("OBS_TEST_REDIS_URL", "").strip()

if TEST_REDIS_URL:
    CACHE_CONFIG = {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": TEST_REDIS_URL,
        "OPTIONS": {
            "socket_connect_timeout": 2,
            "socket_timeout": 2,
            "retry_on_timeout": True,
        },
    }
else:
    CACHE_CONFIG = {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "obs-cache-tests",
    }

CACHED_SETTINGS = {
    "CACHES": {"default": CACHE_CONFIG},
    "CACHE_ENABLED": True,
}


def book_data(**overrides):
    data = {
        "title": "Cached Book",
        "author": "Cache Author",
        "isbn": "9780132350884",
        "description": "A book used by the cache tests.",
        "category": "Fiction",
        "price": Decimal("10.00"),
        "stock_quantity": 5,
    }
    data.update(overrides)
    return data


@override_settings(**CACHED_SETTINGS)
class CachedReadTests(TestCase):
    """Public catalogue reads are served from the cache and invalidated."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.book = Book.objects.create(**book_data())

    def catalogue(self, query=""):
        return self.client.get(f"{reverse('book_list')}{query}")

    def test_a_repeated_read_is_served_from_the_cache(self):
        first = self.catalogue()
        self.assertEqual(first["X-Cache"], "MISS")

        second = self.catalogue()

        self.assertEqual(second["X-Cache"], "HIT")
        self.assertEqual(second.json(), first.json())

    def test_a_cached_read_does_not_see_a_change_made_behind_its_back(self):
        self.catalogue()

        # An ORM write invalidates nothing, which is exactly what makes
        # this a test of the cache rather than of the database.
        Book.objects.filter(pk=self.book.pk).update(title="Renamed")

        self.assertEqual(
            self.catalogue().json()["books"][0]["title"], "Cached Book"
        )

    def test_invalidating_the_namespace_serves_the_change(self):
        self.catalogue()
        Book.objects.filter(pk=self.book.pk).update(title="Renamed")

        cache_module.invalidate(cache_module.BOOKS)

        response = self.catalogue()
        self.assertEqual(response["X-Cache"], "MISS")
        self.assertEqual(response.json()["books"][0]["title"], "Renamed")

    def test_each_query_string_is_cached_separately(self):
        self.catalogue()

        filtered = self.catalogue("?category=Fiction")
        self.assertEqual(filtered["X-Cache"], "MISS")
        self.assertEqual(self.catalogue("?category=Fiction")["X-Cache"], "HIT")

        # A filter that excludes the book must not be answered from the
        # unfiltered entry.
        empty = self.catalogue("?category=History")
        self.assertEqual(empty.json()["count"], 0)

    def test_the_detail_and_list_routes_do_not_share_an_entry(self):
        self.catalogue()

        detail = self.client.get(
            reverse("book_detail", args=[self.book.pk])
        )

        self.assertEqual(detail["X-Cache"], "MISS")
        self.assertEqual(detail.json()["book"]["id"], self.book.pk)

    def test_categories_are_cached_and_invalidated(self):
        self.assertEqual(
            self.client.get(reverse("book_categories")).json()["categories"],
            ["Fiction"],
        )
        self.assertEqual(
            self.client.get(reverse("book_categories"))["X-Cache"], "HIT"
        )

    def test_an_error_response_is_never_cached(self):
        missing = reverse("book_detail", args=[999999])

        self.assertEqual(self.client.get(missing).status_code, 404)
        # Still a miss: a 404 cached in place of a book would survive the
        # book being created.
        self.assertEqual(self.client.get(missing)["X-Cache"], "MISS")

        bad_filter = f"{reverse('book_list')}?min_price=abc"
        self.assertEqual(self.client.get(bad_filter).status_code, 400)
        self.assertEqual(self.client.get(bad_filter)["X-Cache"], "MISS")


@override_settings(**CACHED_SETTINGS)
class CacheWriteInvalidationTests(FirebaseTokenMixin, TestCase):
    """Every write invalidates the reads it changes."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)

        self.book = Book.objects.create(**book_data())
        self.administrator = get_user_model().objects.create_user(
            username="cacheadmin",
            email="cacheadmin@example.com",
            is_staff=True,
        )
        self.admin_token = self.make_token(
            uid="uid-cache-admin", email="cacheadmin@example.com"
        )

    def admin_call(self, method, name, args=None, payload=None):
        return getattr(self.client, method)(
            reverse(name, args=args or []),
            data=json.dumps(payload or {}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_token}",
        )

    def catalogue_titles(self):
        response = self.client.get(reverse("book_list"))
        return [book["title"] for book in response.json()["books"]]

    def test_an_administrator_update_reaches_the_catalogue_at_once(self):
        self.assertEqual(self.catalogue_titles(), ["Cached Book"])

        response = self.admin_call(
            "patch",
            "admin_book_detail",
            args=[self.book.pk],
            payload={"title": "Edited Title"},
        )
        self.assertEqual(response.status_code, 200)

        self.assertEqual(self.catalogue_titles(), ["Edited Title"])

    def test_adding_a_book_reaches_the_catalogue_at_once(self):
        self.catalogue_titles()

        response = self.admin_call(
            "post",
            "admin_book_collection",
            payload={
                **book_data(
                    title="Brand New",
                    isbn="9780201633610",
                    price="12.00",
                ),
                "price": "12.00",
                "publisher": "",
                "publication_date": None,
                "cover_image_url": "",
            },
        )
        self.assertEqual(response.status_code, 201)

        self.assertIn("Brand New", self.catalogue_titles())

    def test_a_review_reaches_the_rating_summary_at_once(self):
        token = self.make_token(uid="uid-reviewer", email="r@example.com")
        reviews_url = f"{reverse('review_collection')}?book={self.book.pk}"

        first = self.client.get(
            reviews_url, HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(first.json()["summary"]["review_count"], 0)

        posted = self.client.post(
            reverse("review_collection"),
            data=json.dumps({"book_id": self.book.pk, "rating": 5}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(posted.status_code, 201)

        after = self.client.get(
            reviews_url, HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(after.json()["summary"]["review_count"], 1)
        self.assertFalse(after.json()["can_review"])

    def test_a_cart_change_reaches_the_cart_at_once(self):
        token = self.make_token(uid="uid-shopper", email="s@example.com")
        auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        self.client.post(
            reverse("api_signin"),
            data=json.dumps({}),
            content_type="application/json",
            **auth,
        )
        self.assertEqual(
            self.client.get(reverse("cart_detail"), **auth)
            .json()["cart"]["item_count"],
            0,
        )

        self.client.post(
            reverse("cart_item_add"),
            data=json.dumps({"book_id": self.book.pk, "quantity": 2}),
            content_type="application/json",
            **auth,
        )

        self.assertEqual(
            self.client.get(reverse("cart_detail"), **auth)
            .json()["cart"]["item_count"],
            2,
        )


@override_settings(**CACHED_SETTINGS)
class CacheScopeTests(FirebaseTokenMixin, TestCase):
    """A cached entry must never cross from one caller to another."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)

        self.book = Book.objects.create(**book_data())

    def sign_in(self, uid, email):
        token = self.make_token(uid=uid, email=email)
        self.client.post(
            reverse("api_signin"),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        return token

    def orders(self, token):
        return self.client.get(
            reverse("order_collection"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        ).json()

    def test_one_customers_orders_are_never_served_to_another(self):
        first = self.sign_in("uid-one", "one@example.com")
        Order.objects.create(
            user=get_user_model().objects.get(email="one@example.com"),
            session_key="one-session",
            total_amount=Decimal("10.00"),
        )

        self.assertEqual(self.orders(first)["count"], 1)
        # Cached now; the second customer must not be given it.
        self.assertEqual(self.orders(first)["count"], 1)

        second = self.sign_in("uid-two", "two@example.com")

        self.assertEqual(self.orders(second)["count"], 0)

    def test_a_customers_cart_is_never_served_to_a_guest(self):
        token = self.sign_in("uid-cart", "cart@example.com")
        auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        self.client.post(
            reverse("cart_item_add"),
            data=json.dumps({"book_id": self.book.pk, "quantity": 3}),
            content_type="application/json",
            **auth,
        )
        self.assertEqual(
            self.client.get(reverse("cart_detail"), **auth)
            .json()["cart"]["item_count"],
            3,
        )

        guest = self.client_class()
        self.assertEqual(
            guest.get(reverse("cart_detail")).json()["cart"]["item_count"],
            0,
        )

    def test_a_caller_with_no_session_is_not_cached(self):
        # Every brand-new visitor would otherwise share one key, so these
        # responses are not cached at all.
        response = self.client_class().get(reverse("cart_detail"))

        self.assertNotIn("X-Cache", response)

    def test_an_administrator_answer_is_not_served_to_a_customer(self):
        get_user_model().objects.create_user(
            username="scopeadmin",
            email="scopeadmin@example.com",
            is_staff=True,
        )
        admin_token = self.make_token(
            uid="uid-scope-admin", email="scopeadmin@example.com"
        )

        allowed = self.client.get(
            reverse("admin_book_collection"),
            HTTP_AUTHORIZATION=f"Bearer {admin_token}",
        )
        self.assertEqual(allowed.status_code, 200)

        customer_token = self.make_token(
            uid="uid-scope-customer", email="customer@example.com"
        )
        refused = self.client.get(
            reverse("admin_book_collection"),
            HTTP_AUTHORIZATION=f"Bearer {customer_token}",
        )

        # staff_required_api wraps the cache, so the customer is refused
        # before any lookup and is never handed the cached answer.
        self.assertEqual(refused.status_code, 403)
        self.assertNotIn("X-Cache", refused)

    def test_identity_and_token_endpoints_are_never_cached(self):
        token = self.sign_in("uid-identity", "identity@example.com")

        session = self.client.get(
            reverse("api_session_detail"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        csrf = self.client.get(reverse("csrf_token"))
        health = self.client.get(reverse("healthz"))

        for response in (session, csrf, health):
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("X-Cache", response)


@override_settings(**CACHED_SETTINGS)
class CacheResilienceTests(TestCase):
    """A cache that misbehaves must slow the API, never break it."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.book = Book.objects.create(**book_data())

    def test_a_read_failure_degrades_to_a_miss(self):
        with mock.patch.object(
            cache_module.cache, "get_many", side_effect=OSError("no route")
        ):
            response = self.client.get(reverse("book_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

    def test_a_write_failure_does_not_fail_the_request(self):
        with mock.patch.object(
            cache_module.cache, "set", side_effect=OSError("no route")
        ):
            response = self.client.get(reverse("book_list"))

        self.assertEqual(response.status_code, 200)

    def test_an_invalidation_failure_does_not_fail_the_write(self):
        with mock.patch.object(
            cache_module.cache, "set_many", side_effect=OSError("no route")
        ):
            # The data is already committed by this point; losing the
            # invalidation must not turn a successful write into a 500.
            cache_module.invalidate(cache_module.BOOKS)

    def test_an_evicted_namespace_token_invalidates_rather_than_serves_stale(
        self,
    ):
        self.client.get(reverse("book_list"))
        Book.objects.filter(pk=self.book.pk).update(title="Renamed")

        # Upstash evicts under memory pressure. A lost version token must
        # make its entries unreachable, not resurrect them.
        cache.delete(f"{cache_module.KEY_PREFIX}:ns:{cache_module.BOOKS}")

        response = self.client.get(reverse("book_list"))

        self.assertEqual(response["X-Cache"], "MISS")
        self.assertEqual(response.json()["books"][0]["title"], "Renamed")


class CacheDisabledTests(TestCase):
    """With no Redis configured, nothing is cached at all."""

    def setUp(self):
        self.book = Book.objects.create(**book_data())

    def test_reads_are_not_cached(self):
        # config.settings_test leaves CACHE_ENABLED off, as a deployment
        # without REDIS_URL does.
        response = self.client.get(reverse("book_list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("X-Cache", response)

    def test_invalidate_is_a_no_op(self):
        cache_module.invalidate(cache_module.BOOKS, cache_module.ORDERS)

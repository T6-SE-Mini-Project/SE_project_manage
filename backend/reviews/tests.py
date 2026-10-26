"""Tests for book reviews (issue #11, OBS-F-016, TC-OBS-016)."""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from books.models import Book

from .models import Review


def book_data(**overrides):
    data = {
        "title": "Review Book",
        "author": "Review Author",
        "isbn": "9780132350884",
        "description": "A book used by review tests.",
        "category": "Fiction",
        "price": Decimal("20.00"),
        "stock_quantity": 4,
    }
    data.update(overrides)
    return data


class ReviewSubmissionTests(TestCase):
    """TC-OBS-016: customers can submit reviews for a book."""

    def setUp(self):
        self.book = Book.objects.create(**book_data())
        self.user = get_user_model().objects.create_user(
            username="reviewer",
            email="reviewer@example.com",
            password="ReviewerPass123",
        )

    def submit(self, payload):
        return self.client.post(
            reverse("review_collection"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def valid_payload(self, **overrides):
        payload = {
            "book_id": self.book.pk,
            "rating": 5,
            "title": "A great read",
            "comment": "Clear, practical and well written.",
        }
        payload.update(overrides)
        return payload

    def test_signed_in_customer_can_submit_a_review(self):
        self.client.force_login(self.user)

        response = self.submit(self.valid_payload())

        self.assertEqual(response.status_code, 201)
        body = response.json()

        review = body["review"]
        self.assertEqual(review["rating"], 5)
        self.assertEqual(review["title"], "A great read")
        self.assertEqual(review["comment"], "Clear, practical and well written.")
        self.assertEqual(review["author"], "reviewer")
        self.assertTrue(review["is_owner"])

        self.assertEqual(body["summary"]["review_count"], 1)
        self.assertEqual(body["summary"]["average_rating"], "5.0")

        stored = Review.objects.get(pk=review["id"])
        self.assertEqual(stored.book_id, self.book.pk)
        self.assertEqual(stored.user_id, self.user.pk)

    def test_review_without_a_comment_is_accepted(self):
        self.client.force_login(self.user)

        response = self.submit(
            self.valid_payload(title="", comment="")
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["review"]["comment"], "")

    def test_anonymous_submission_is_rejected(self):
        response = self.submit(self.valid_payload())

        self.assertEqual(response.status_code, 401)
        self.assertFalse(Review.objects.exists())

    def test_rating_is_required(self):
        self.client.force_login(self.user)

        response = self.submit(self.valid_payload(rating=None))

        self.assertEqual(response.status_code, 400)
        self.assertIn("rating", response.json()["errors"])
        self.assertFalse(Review.objects.exists())

    def test_rating_outside_the_allowed_range_is_rejected(self):
        self.client.force_login(self.user)

        for rating in (0, 6, -2, 99):
            with self.subTest(rating=rating):
                response = self.submit(self.valid_payload(rating=rating))
                self.assertEqual(response.status_code, 400)
                self.assertIn("rating", response.json()["errors"])

        self.assertFalse(Review.objects.exists())

    def test_non_numeric_rating_is_rejected(self):
        self.client.force_login(self.user)

        response = self.submit(self.valid_payload(rating="excellent"))

        self.assertEqual(response.status_code, 400)
        self.assertIn("rating", response.json()["errors"])

    def test_overlong_title_and_comment_are_rejected(self):
        self.client.force_login(self.user)

        response = self.submit(self.valid_payload(title="x" * 121))
        self.assertEqual(response.status_code, 400)
        self.assertIn("title", response.json()["errors"])

        response = self.submit(
            self.valid_payload(comment="y" * (Review.MAX_COMMENT_LENGTH + 1))
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("comment", response.json()["errors"])

    def test_review_for_an_unknown_book_returns_404(self):
        self.client.force_login(self.user)

        response = self.submit(self.valid_payload(book_id=999999))

        self.assertEqual(response.status_code, 404)

    def test_missing_book_id_is_rejected(self):
        self.client.force_login(self.user)

        response = self.submit(self.valid_payload(book_id=None))

        self.assertEqual(response.status_code, 400)
        self.assertIn("book_id", response.json()["error"])

    def test_invalid_json_body_is_rejected(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("review_collection"),
            data="not json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_a_customer_can_only_review_a_book_once(self):
        self.client.force_login(self.user)

        self.assertEqual(self.submit(self.valid_payload()).status_code, 201)

        response = self.submit(self.valid_payload(rating=1))

        self.assertEqual(response.status_code, 409)
        self.assertIn("already reviewed", response.json()["error"])
        self.assertEqual(Review.objects.count(), 1)


class ReviewDisplayTests(TestCase):
    """The system displays submitted reviews and the aggregate rating."""

    def setUp(self):
        self.book = Book.objects.create(**book_data())
        self.other_book = Book.objects.create(
            **book_data(title="Other Book", isbn="9780201633610")
        )

        User = get_user_model()
        self.first = User.objects.create_user(
            username="firstreader",
            email="first@example.com",
            password="FirstPass123",
        )
        self.second = User.objects.create_user(
            username="secondreader",
            email="second@example.com",
            password="SecondPass123",
        )

        Review.objects.create(
            book=self.book, user=self.first, rating=4, comment="Good"
        )
        Review.objects.create(
            book=self.book, user=self.second, rating=5, comment="Excellent"
        )
        Review.objects.create(
            book=self.other_book, user=self.first, rating=1, comment="No"
        )

    def listing(self, book_id=None):
        response = self.client.get(
            reverse("review_collection"),
            {"book": book_id or self.book.pk},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_reviews_are_listed_for_the_requested_book(self):
        body = self.listing()

        self.assertEqual(len(body["reviews"]), 2)
        self.assertEqual(
            {review["comment"] for review in body["reviews"]},
            {"Good", "Excellent"},
        )

    def test_summary_reports_average_and_distribution(self):
        summary = self.listing()["summary"]

        self.assertEqual(summary["review_count"], 2)
        self.assertEqual(summary["average_rating"], "4.5")
        self.assertEqual(summary["rating_counts"]["5"], 1)
        self.assertEqual(summary["rating_counts"]["4"], 1)
        self.assertEqual(summary["rating_counts"]["3"], 0)

    def test_book_without_reviews_reports_no_average(self):
        fresh = Book.objects.create(
            **book_data(title="Unrated", isbn="9781491950357")
        )

        summary = self.listing(fresh.pk)["summary"]

        self.assertEqual(summary["review_count"], 0)
        self.assertIsNone(summary["average_rating"])

    def test_reviews_are_public(self):
        body = self.listing()

        self.assertFalse(body["can_review"])
        self.assertIsNone(body["my_review"])
        self.assertFalse(
            any(review["is_owner"] for review in body["reviews"])
        )

    def test_signed_in_customer_sees_their_own_review(self):
        self.client.force_login(self.first)

        body = self.listing()

        self.assertFalse(body["can_review"])
        self.assertEqual(body["my_review"]["comment"], "Good")
        self.assertTrue(body["my_review"]["is_owner"])

    def test_customer_without_a_review_can_submit_one(self):
        third = get_user_model().objects.create_user(
            username="thirdreader",
            email="third@example.com",
            password="ThirdPass123",
        )
        self.client.force_login(third)

        body = self.listing()

        self.assertTrue(body["can_review"])
        self.assertIsNone(body["my_review"])

    def test_listing_requires_a_book_reference(self):
        response = self.client.get(reverse("review_collection"))

        self.assertEqual(response.status_code, 400)
        self.assertIn("book", response.json()["error"])

    def test_listing_for_an_unknown_book_returns_404(self):
        response = self.client.get(
            reverse("review_collection"), {"book": 999999}
        )

        self.assertEqual(response.status_code, 404)

    def test_deleting_the_book_removes_its_reviews(self):
        self.other_book.delete()

        self.assertFalse(Review.objects.filter(book_id=self.other_book.pk))


class ReviewEditTests(TestCase):
    """Customers manage their own review; administrators moderate."""

    def setUp(self):
        self.book = Book.objects.create(**book_data())

        User = get_user_model()
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="OwnerPass123",
        )
        self.other = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="OtherPass123",
        )
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="AdminPass123",
            is_staff=True,
        )

        self.review = Review.objects.create(
            book=self.book,
            user=self.owner,
            rating=3,
            title="Fine",
            comment="It was fine.",
        )

    def patch(self, payload, review_id=None):
        return self.client.patch(
            reverse("review_detail", args=[review_id or self.review.pk]),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def delete(self, review_id=None):
        return self.client.delete(
            reverse("review_detail", args=[review_id or self.review.pk])
        )

    def test_owner_can_edit_their_review(self):
        self.client.force_login(self.owner)

        response = self.patch({"rating": 5, "comment": "Better than I said."})

        self.assertEqual(response.status_code, 200)
        review = response.json()["review"]

        self.assertEqual(review["rating"], 5)
        self.assertEqual(review["comment"], "Better than I said.")
        self.assertEqual(response.json()["summary"]["average_rating"], "5.0")

        self.review.refresh_from_db()
        self.assertEqual(self.review.rating, 5)

    def test_partial_edit_keeps_the_other_fields(self):
        self.client.force_login(self.owner)

        self.assertEqual(self.patch({"rating": 4}).status_code, 200)

        self.review.refresh_from_db()
        self.assertEqual(self.review.rating, 4)
        self.assertEqual(self.review.comment, "It was fine.")

    def test_edit_validates_the_rating(self):
        self.client.force_login(self.owner)

        response = self.patch({"rating": 9})

        self.assertEqual(response.status_code, 400)
        self.review.refresh_from_db()
        self.assertEqual(self.review.rating, 3)

    def test_edit_without_fields_is_rejected(self):
        self.client.force_login(self.owner)

        response = self.patch({})

        self.assertEqual(response.status_code, 400)

    def test_another_customer_cannot_edit_the_review(self):
        self.client.force_login(self.other)

        response = self.patch({"rating": 1})

        self.assertEqual(response.status_code, 403)
        self.review.refresh_from_db()
        self.assertEqual(self.review.rating, 3)

    def test_anonymous_caller_cannot_edit_the_review(self):
        response = self.patch({"rating": 1})

        self.assertEqual(response.status_code, 401)

    def test_owner_can_delete_their_review(self):
        self.client.force_login(self.owner)

        response = self.delete()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["summary"]["review_count"], 0)
        self.assertFalse(Review.objects.filter(pk=self.review.pk).exists())

    def test_administrator_can_remove_any_review(self):
        self.client.force_login(self.admin)

        response = self.delete()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Review.objects.filter(pk=self.review.pk).exists())

    def test_administrator_cannot_rewrite_a_customers_review(self):
        self.client.force_login(self.admin)

        response = self.patch({"rating": 1})

        self.assertEqual(response.status_code, 403)

    def test_another_customer_cannot_delete_the_review(self):
        self.client.force_login(self.other)

        self.assertEqual(self.delete().status_code, 403)
        self.assertTrue(Review.objects.filter(pk=self.review.pk).exists())

    def test_unknown_review_returns_404(self):
        self.client.force_login(self.owner)

        self.assertEqual(self.delete(999999).status_code, 404)

    def test_unsupported_method_is_rejected(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("review_detail", args=[self.review.pk])
        )

        self.assertEqual(response.status_code, 405)

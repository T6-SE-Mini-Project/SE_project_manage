import math
import time
from decimal import Decimal
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import Book


def build_book(**overrides):
    data = {
        "title": "Test Book",
        "author": "Test Author",
        "isbn": "9780132350884",
        "description": "A book used by the automated tests.",
        "category": "Software Engineering",
        "price": Decimal("42.50"),
        "stock_quantity": 4,
        "cover_image_url": (
            "https://covers.openlibrary.org/b/isbn/9780132350884-L.jpg"
        ),
        "publisher": "Test Publisher",
    }
    data.update(overrides)
    return Book(**data)


class BookModelTests(TestCase):
    def test_string_representation_returns_title(self):
        book = build_book(title="Clean Code")

        self.assertEqual(str(book), "Clean Code")

    def test_in_stock_is_true_when_stock_is_positive(self):
        book = build_book(stock_quantity=1)

        self.assertTrue(book.in_stock)

    def test_in_stock_is_false_when_stock_is_zero(self):
        book = build_book(stock_quantity=0)

        self.assertFalse(book.in_stock)

    def test_isbn_is_normalized_on_save(self):
        book = build_book(isbn="978-0-13-235088-4")
        book.save()

        book.refresh_from_db()

        self.assertEqual(book.isbn, "9780132350884")

    def test_invalid_isbn_is_rejected(self):
        book = build_book(isbn="123")

        with self.assertRaises(ValidationError):
            book.full_clean()

    def test_negative_price_is_rejected(self):
        book = build_book(price=Decimal("-1.00"))

        with self.assertRaises(ValidationError):
            book.full_clean()

    def test_isbn_must_be_unique(self):
        build_book().save()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                build_book(title="Another Book").save()


class BookApiTests(TestCase):
    """TC-OBS-003 (browse) and TC-OBS-006 (book details)."""

    @classmethod
    def setUpTestData(cls):
        cls.alpha = build_book(
            title="Alpha Book",
            isbn="9780132350884",
            stock_quantity=4,
        )
        cls.alpha.save()

        cls.beta = build_book(
            title="Beta Book",
            author="Another Author",
            isbn="9780201633610",
            category="Programming",
            price=Decimal("19.99"),
            stock_quantity=0,
        )
        cls.beta.save()

    def test_catalogue_returns_all_books_in_model_order(self):
        response = self.client.get(reverse("book_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

        payload = response.json()

        self.assertEqual(payload["count"], 2)
        self.assertEqual(
            [book["title"] for book in payload["books"]],
            ["Alpha Book", "Beta Book"],
        )

    def test_catalogue_returns_summary_fields(self):
        response = self.client.get(reverse("book_list"))

        book = response.json()["books"][0]

        self.assertEqual(
            set(book),
            {
                "id",
                "title",
                "author",
                "isbn",
                "category",
                "price",
                "stock_quantity",
                "in_stock",
                "cover_image_url",
            },
        )
        self.assertEqual(book["price"], "42.50")
        self.assertTrue(book["in_stock"])

    def test_details_return_book_information(self):
        response = self.client.get(
            reverse("book_detail", args=[self.alpha.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

        book = response.json()["book"]

        self.assertEqual(book["id"], self.alpha.pk)
        self.assertEqual(book["title"], "Alpha Book")
        self.assertEqual(
            book["description"],
            "A book used by the automated tests.",
        )
        self.assertEqual(book["publisher"], "Test Publisher")
        self.assertIsNone(book["publication_date"])
        self.assertIn("created_at", book)
        self.assertIn("updated_at", book)

    def test_unknown_book_returns_json_404(self):
        response = self.client.get(
            reverse("book_detail", args=[999999])
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response.json(), {"error": "Book not found."})


class SeedBooksCommandTests(TestCase):
    def test_seed_books_creates_catalogue_and_is_idempotent(self):
        call_command("seed_books", stdout=StringIO())

        first_count = Book.objects.count()

        self.assertEqual(first_count, 7)

        call_command("seed_books", stdout=StringIO())

        self.assertEqual(Book.objects.count(), first_count)


class BookSearchFilterTests(TestCase):
    """TC-OBS-004 (search) and TC-OBS-005 (filters)."""

    @classmethod
    def setUpTestData(cls):
        cls.alpha = build_book(
            title="Alpha Adventure",
            author="Alice Author",
            isbn="9780132350884",
            description="A space adventure for test readers.",
            category="Fiction",
            price=Decimal("10.00"),
            stock_quantity=5,
        )
        cls.alpha.save()

        cls.beta = build_book(
            title="Beta Handbook",
            author="Bob Writer",
            isbn="9780201633610",
            description="A practical handbook for test readers.",
            category="Nonfiction",
            price=Decimal("20.00"),
            stock_quantity=0,
        )
        cls.beta.save()

        cls.gamma = build_book(
            title="Gamma Tales",
            author="Alice Author",
            isbn="9780134685991",
            description="Short stories for test readers.",
            category="Fiction",
            price=Decimal("30.00"),
            stock_quantity=2,
        )
        cls.gamma.save()

    def titles(self, response):
        return [book["title"] for book in response.json()["books"]]

    def test_search_by_title(self):
        response = self.client.get(reverse("book_list"), {"q": "Alpha"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.titles(response), ["Alpha Adventure"])

    def test_search_by_author(self):
        response = self.client.get(reverse("book_list"), {"q": "Alice"})

        self.assertEqual(
            self.titles(response),
            ["Alpha Adventure", "Gamma Tales"],
        )

    def test_search_by_isbn(self):
        response = self.client.get(reverse("book_list"), {"q": "978020"})

        self.assertEqual(self.titles(response), ["Beta Handbook"])

    def test_search_by_description_keyword(self):
        response = self.client.get(reverse("book_list"), {"q": "handbook"})

        self.assertEqual(self.titles(response), ["Beta Handbook"])

    def test_filter_by_category(self):
        response = self.client.get(
            reverse("book_list"),
            {"category": "Fiction"},
        )

        self.assertEqual(
            self.titles(response),
            ["Alpha Adventure", "Gamma Tales"],
        )

    def test_filter_by_author(self):
        response = self.client.get(reverse("book_list"), {"author": "Alice"})

        self.assertEqual(
            self.titles(response),
            ["Alpha Adventure", "Gamma Tales"],
        )

    def test_filter_by_price_range(self):
        response = self.client.get(
            reverse("book_list"),
            {"min_price": "15.00", "max_price": "25.00"},
        )

        self.assertEqual(self.titles(response), ["Beta Handbook"])

    def test_filter_by_availability(self):
        response = self.client.get(
            reverse("book_list"),
            {"available": "true"},
        )
        self.assertEqual(
            self.titles(response),
            ["Alpha Adventure", "Gamma Tales"],
        )

        response = self.client.get(
            reverse("book_list"),
            {"available": "false"},
        )
        self.assertEqual(self.titles(response), ["Beta Handbook"])

    def test_filters_combine(self):
        response = self.client.get(
            reverse("book_list"),
            {
                "category": "Fiction",
                "available": "true",
                "max_price": "25.00",
            },
        )

        self.assertEqual(self.titles(response), ["Alpha Adventure"])

    def test_invalid_price_filter_is_rejected(self):
        response = self.client.get(
            reverse("book_list"),
            {"min_price": "not-a-number"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("error", response.json())

    def test_inverted_price_range_is_rejected(self):
        response = self.client.get(
            reverse("book_list"),
            {"min_price": "50.00", "max_price": "10.00"},
        )

        self.assertEqual(response.status_code, 400)

    def test_invalid_availability_filter_is_rejected(self):
        response = self.client.get(
            reverse("book_list"),
            {"available": "maybe"},
        )

        self.assertEqual(response.status_code, 400)

    def test_categories_endpoint_returns_distinct_categories(self):
        response = self.client.get(reverse("book_categories"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["categories"],
            ["Fiction", "Nonfiction"],
        )


class SearchPerformanceTests(TestCase):
    """TC-OBS-019 (OBS-NF-001): 90% of searches complete within 3 seconds."""

    REQUEST_COUNT = 20
    THRESHOLD_SECONDS = 3.0

    @classmethod
    def setUpTestData(cls):
        books = []
        for index in range(40):
            books.append(
                build_book(
                    title=f"Performance Title {index}",
                    author=f"Author {index % 5}",
                    isbn=f"978000000{index:04d}",
                    description=f"Performance description {index}",
                    category=f"Category {index % 4}",
                    price=Decimal("10.00") + index,
                    stock_quantity=index % 3,
                )
            )
        Book.objects.bulk_create(books)

    def test_search_response_time_target(self):
        queries = [
            "performance",
            "Author 1",
            "9780000000010",
            "Title 2",
            "",
        ]

        durations = []
        for index in range(self.REQUEST_COUNT):
            start = time.perf_counter()
            response = self.client.get(
                reverse("book_list"),
                {"q": queries[index % len(queries)]},
            )
            durations.append(time.perf_counter() - start)

            self.assertEqual(response.status_code, 200)

        within_threshold = sum(
            1
            for duration in durations
            if duration <= self.THRESHOLD_SECONDS
        )
        required = math.ceil(self.REQUEST_COUNT * 0.9)
        ordered = sorted(durations)
        p90 = ordered[required - 1]

        print(
            "\nTC-OBS-019 search timings (seconds): "
            f"min={ordered[0]:.4f} p90={p90:.4f} "
            f"max={ordered[-1]:.4f}; "
            f"{within_threshold}/{self.REQUEST_COUNT} within "
            f"{self.THRESHOLD_SECONDS:.1f}s"
        )

        self.assertGreaterEqual(within_threshold, required)

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from books.models import Book


SAMPLE_BOOKS = [
    {
        "isbn": "9780132350884",
        "title": "Clean Code",
        "author": "Robert C. Martin",
        "category": "Software Engineering",
        "price": Decimal("42.50"),
        "stock_quantity": 12,
        "cover_image_url": (
            "https://covers.openlibrary.org/b/isbn/9780132350884-L.jpg"
        ),
        "publisher": "Prentice Hall",
        "publication_date": date(2008, 8, 1),
        "description": (
            "A practical guide to writing readable, maintainable code, "
            "covering naming, functions, formatting, testing and refactoring."
        ),
    },
    {
        "isbn": "9780201633610",
        "title": "Design Patterns: Elements of Reusable Object-Oriented Software",
        "author": "Erich Gamma, Richard Helm, Ralph Johnson, John Vlissides",
        "category": "Software Engineering",
        "price": Decimal("54.99"),
        "stock_quantity": 5,
        "cover_image_url": (
            "https://covers.openlibrary.org/b/isbn/9780201633610-L.jpg"
        ),
        "publisher": "Addison-Wesley",
        "publication_date": date(1994, 10, 31),
        "description": (
            "The classic catalogue of object-oriented design patterns, "
            "organised into creational, structural and behavioural groups."
        ),
    },
    {
        "isbn": "9780134685991",
        "title": "Effective Java",
        "author": "Joshua Bloch",
        "category": "Programming",
        "price": Decimal("47.99"),
        "stock_quantity": 8,
        "cover_image_url": (
            "https://covers.openlibrary.org/b/isbn/9780134685991-L.jpg"
        ),
        "publisher": "Addison-Wesley",
        "publication_date": date(2017, 12, 27),
        "description": (
            "Ninety best practices for writing clear, correct and "
            "maintainable Java code, updated for modern Java releases."
        ),
    },
    {
        "isbn": "9781491950296",
        "title": "Designing Data-Intensive Applications",
        "author": "Martin Kleppmann",
        "category": "Data Engineering",
        "price": Decimal("59.99"),
        "stock_quantity": 3,
        "cover_image_url": (
            "https://covers.openlibrary.org/b/isbn/9781491950296-L.jpg"
        ),
        "publisher": "O'Reilly Media",
        "publication_date": date(2017, 3, 16),
        "description": (
            "An overview of the principles behind reliable, scalable and "
            "maintainable distributed data systems."
        ),
    },
    {
        "isbn": "9780596007126",
        "title": "Head First Design Patterns",
        "author": "Eric Freeman, Elisabeth Robson",
        "category": "Software Engineering",
        "price": Decimal("39.99"),
        "stock_quantity": 0,
        "cover_image_url": (
            "https://covers.openlibrary.org/b/isbn/9780596007126-L.jpg"
        ),
        "publisher": "O'Reilly Media",
        "publication_date": date(2004, 10, 25),
        "description": (
            "A visual, example-driven introduction to design patterns for "
            "object-oriented software."
        ),
    },
    {
        "isbn": "9780201616224",
        "title": "The Pragmatic Programmer",
        "author": "Andrew Hunt, David Thomas",
        "category": "Software Engineering",
        "price": Decimal("44.99"),
        "stock_quantity": 10,
        "cover_image_url": (
            "https://covers.openlibrary.org/b/isbn/9780201616224-L.jpg"
        ),
        "publisher": "Addison-Wesley",
        "publication_date": date(1999, 10, 30),
        "description": (
            "Practical advice on the craft of software development, from "
            "personal responsibility to tooling and delivery."
        ),
    },
    {
        "isbn": "9780131103627",
        "title": "The C Programming Language",
        "author": "Brian W. Kernighan, Dennis M. Ritchie",
        "category": "Programming",
        "price": Decimal("35.00"),
        "stock_quantity": 7,
        "cover_image_url": (
            "https://covers.openlibrary.org/b/isbn/9780131103627-L.jpg"
        ),
        "publisher": "Prentice Hall",
        "publication_date": date(1988, 4, 1),
        "description": (
            "The concise reference and tutorial for the C language by its "
            "original authors."
        ),
    },
]


class Command(BaseCommand):
    help = "Create or update the sample book catalogue (safe to re-run)."

    @transaction.atomic
    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for book_data in SAMPLE_BOOKS:
            data = dict(book_data)
            isbn = data.pop("isbn")
            _, created = Book.objects.update_or_create(
                isbn=isbn,
                defaults=data,
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Sample catalogue ready: "
                f"{created_count} created, {updated_count} updated."
            )
        )

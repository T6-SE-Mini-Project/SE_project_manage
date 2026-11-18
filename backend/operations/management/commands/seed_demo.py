"""Populate the store with a realistic demo dataset.

The production catalogue is empty apart from what an administrator adds by
hand, which makes every screen look broken during a demo. This command
creates a believable store instead:

* a wider book catalogue (on top of ``seed_books``),
* an administrator, a manager and eight customers, each with a Firebase
  identity so the admin lists have something to show,
* carts, reviews, orders in every lifecycle state, and payments,
* order timestamps spread over the last few weeks so the sales report has
  a trend line rather than one spike.

It is safe to re-run: every row is keyed by something stable (username,
ISBN, cart session key, review book+user, demo order marker), so a second
run updates rather than duplicates. Existing real users and orders are
never touched.

    python manage.py seed_demo

The demo accounts all share the password ``DemoPass123!`` unless
``--password`` is given. That password is only useful for the Django admin
at /admin/: customers sign in through Firebase, not with a Django password.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from accounts.models import FirebaseIdentity
from books.models import Book
from cart.models import Cart, CartItem
from orders.models import Order, OrderItem
from payments.models import Payment
from reviews.models import Review

DEMO_PASSWORD = "DemoPass123!"

#: Stable marker so a re-run finds its own orders instead of adding more.
ORDER_MARKER = "seed-demo-order-"

#: ``isbn`` is the stable key, so the catalogue can grow without duplicating.
EXTRA_BOOKS = [
    {
        "isbn": "9780134757599",
        "title": "Refactoring: Improving the Design of Existing Code",
        "author": "Martin Fowler",
        "category": "Software Engineering",
        "price": Decimal("49.99"),
        "stock_quantity": 14,
        "publisher": "Addison-Wesley",
        "publication_date": date(2018, 11, 20),
        "description": (
            "A catalogue of refactorings and the discipline for applying "
            "them safely, with examples in JavaScript."
        ),
    },
    {
        "isbn": "9780735619678",
        "title": "Code Complete",
        "author": "Steve McConnell",
        "category": "Software Engineering",
        "price": Decimal("44.95"),
        "stock_quantity": 9,
        "publisher": "Microsoft Press",
        "publication_date": date(2004, 6, 9),
        "description": (
            "A practical handbook of software construction, from naming "
            "and control flow to debugging and integration."
        ),
    },
    {
        "isbn": "9780262046305",
        "title": "Introduction to Algorithms",
        "author": "Thomas H. Cormen, Charles E. Leiserson, Ronald L. Rivest, Clifford Stein",
        "category": "Algorithms",
        "price": Decimal("89.99"),
        "stock_quantity": 6,
        "publisher": "MIT Press",
        "publication_date": date(2022, 4, 5),
        "description": (
            "The standard reference on algorithms, covering analysis, "
            "data structures, graphs, dynamic programming and more."
        ),
    },
    {
        "isbn": "9780201896831",
        "title": "The Art of Computer Programming, Volume 1",
        "author": "Donald E. Knuth",
        "category": "Algorithms",
        "price": Decimal("74.99"),
        "stock_quantity": 4,
        "publisher": "Addison-Wesley",
        "publication_date": date(1997, 7, 4),
        "description": (
            "Fundamental algorithms and the mathematical techniques used "
            "to analyse them, from the author of TeX."
        ),
    },
    {
        "isbn": "9780078022159",
        "title": "Database System Concepts",
        "author": "Abraham Silberschatz, Henry F. Korth, S. Sudarshan",
        "category": "Databases",
        "price": Decimal("67.50"),
        "stock_quantity": 7,
        "publisher": "McGraw-Hill",
        "publication_date": date(2019, 2, 19),
        "description": (
            "Relational modelling, SQL, transaction processing and storage "
            "internals, with exercises for each chapter."
        ),
    },
    {
        "isbn": "9781492057611",
        "title": "Learning SQL",
        "author": "Alan Beaulieu",
        "category": "Databases",
        "price": Decimal("39.99"),
        "stock_quantity": 18,
        "publisher": "O'Reilly Media",
        "publication_date": date(2020, 4, 21),
        "description": (
            "A hands-on introduction to SQL queries, joins, subqueries and "
            "transactions for people new to relational databases."
        ),
    },
    {
        "isbn": "9781491963418",
        "title": "PostgreSQL: Up and Running",
        "author": "Regina O. Obe, Leo S. Hsu",
        "category": "Databases",
        "price": Decimal("42.99"),
        "stock_quantity": 11,
        "publisher": "O'Reilly Media",
        "publication_date": date(2017, 12, 12),
        "description": (
            "A fast-paced guide to installing, configuring and operating "
            "PostgreSQL, including replication and JSON support."
        ),
    },
    {
        "isbn": "9781735467207",
        "title": "Django for Beginners",
        "author": "William S. Vincent",
        "category": "Web Development",
        "price": Decimal("36.00"),
        "stock_quantity": 22,
        "publisher": "Welcome to Code",
        "publication_date": date(2022, 9, 1),
        "description": (
            "Build and deploy Django applications step by step, from the "
            "first view to authentication and production deployment."
        ),
    },
    {
        "isbn": "9781491991732",
        "title": "Flask Web Development",
        "author": "Miguel Grinberg",
        "category": "Web Development",
        "price": Decimal("41.99"),
        "stock_quantity": 13,
        "publisher": "O'Reilly Media",
        "publication_date": date(2018, 4, 3),
        "description": (
            "Developing web applications with Flask, covering templates, "
            "databases, authentication, forms and testing."
        ),
    },
    {
        "isbn": "9781491929124",
        "title": "Site Reliability Engineering",
        "author": "Betsy Beyer, Chris Jones, Jennifer Petoff, Niall Richard Murphy",
        "category": "Systems",
        "price": Decimal("54.99"),
        "stock_quantity": 8,
        "publisher": "O'Reilly Media",
        "publication_date": date(2016, 4, 12),
        "description": (
            "How Google runs production systems: service level objectives, "
            "monitoring, on-call, release engineering and postmortems."
        ),
    },
    {
        "isbn": "9780988262591",
        "title": "The Phoenix Project",
        "author": "Gene Kim, Kevin Behr, George Spafford",
        "category": "Business",
        "price": Decimal("24.99"),
        "stock_quantity": 16,
        "publisher": "IT Revolution Press",
        "publication_date": date(2018, 2, 6),
        "description": (
            "A novel about IT operations, DevOps and the flow of work "
            "through a struggling organisation."
        ),
    },
    {
        "isbn": "9780201835953",
        "title": "The Mythical Man-Month",
        "author": "Frederick P. Brooks Jr.",
        "category": "Software Engineering",
        "price": Decimal("34.99"),
        "stock_quantity": 10,
        "publisher": "Addison-Wesley",
        "publication_date": date(1995, 8, 2),
        "description": (
            "Classic essays on software project management, including why "
            "adding people to a late project makes it later."
        ),
    },
    {
        "isbn": "9781455586691",
        "title": "Deep Work",
        "author": "Cal Newport",
        "category": "Productivity",
        "price": Decimal("21.99"),
        "stock_quantity": 25,
        "publisher": "Grand Central Publishing",
        "publication_date": date(2016, 1, 5),
        "description": (
            "Rules for cultivating focused, distraction-free work in a "
            "world of constant interruption."
        ),
    },
    {
        "isbn": "9780735211292",
        "title": "Atomic Habits",
        "author": "James Clear",
        "category": "Productivity",
        "price": Decimal("23.99"),
        "stock_quantity": 30,
        "publisher": "Avery",
        "publication_date": date(2018, 10, 16),
        "description": (
            "A practical framework for building good habits and breaking "
            "bad ones through small, compounding changes."
        ),
    },
    {
        "isbn": "9780062316097",
        "title": "Sapiens: A Brief History of Humankind",
        "author": "Yuval Noah Harari",
        "category": "History",
        "price": Decimal("26.99"),
        "stock_quantity": 19,
        "publisher": "Harper",
        "publication_date": date(2015, 2, 10),
        "description": (
            "A sweeping history of Homo sapiens, from foraging bands to "
            "empires, money, science and the modern world."
        ),
    },
    {
        "isbn": "9780804139298",
        "title": "Zero to One",
        "author": "Peter Thiel, Blake Masters",
        "category": "Business",
        "price": Decimal("22.99"),
        "stock_quantity": 21,
        "publisher": "Crown Business",
        "publication_date": date(2014, 9, 16),
        "description": (
            "Notes on startups and how to build companies that create new "
            "things rather than copying what already exists."
        ),
    },
    {
        "isbn": "9780307887894",
        "title": "The Lean Startup",
        "author": "Eric Ries",
        "category": "Business",
        "price": Decimal("25.99"),
        "stock_quantity": 17,
        "publisher": "Crown Business",
        "publication_date": date(2011, 9, 13),
        "description": (
            "How to validate a product with build-measure-learn loops and "
            "avoid wasting effort on something nobody wants."
        ),
    },
    {
        "isbn": "9780441172719",
        "title": "Dune",
        "author": "Frank Herbert",
        "category": "Fiction",
        "price": Decimal("19.99"),
        "stock_quantity": 24,
        "publisher": "Ace",
        "publication_date": date(1990, 9, 1),
        "description": (
            "Politics, ecology and prophecy collide on the desert planet "
            "Arrakis, the only source of the spice melange."
        ),
    },
    {
        "isbn": "9780593135204",
        "title": "Project Hail Mary",
        "author": "Andy Weir",
        "category": "Fiction",
        "price": Decimal("28.99"),
        "stock_quantity": 15,
        "publisher": "Ballantine Books",
        "publication_date": date(2021, 5, 4),
        "description": (
            "A lone astronaut wakes up far from Earth and has to solve an "
            "impossible problem to save humanity."
        ),
    },
    {
        "isbn": "9780451524935",
        "title": "1984",
        "author": "George Orwell",
        "category": "Fiction",
        "price": Decimal("14.99"),
        "stock_quantity": 27,
        "publisher": "Signet Classics",
        "publication_date": date(1961, 1, 1),
        "description": (
            "A dystopian novel about surveillance, language and power in "
            "the totalitarian state of Oceania."
        ),
    },
    {
        "isbn": "9780553418026",
        "title": "The Martian",
        "author": "Andy Weir",
        "category": "Fiction",
        "price": Decimal("18.99"),
        "stock_quantity": 20,
        "publisher": "Broadway Books",
        "publication_date": date(2014, 2, 11),
        "description": (
            "An astronaut stranded on Mars uses engineering and botany to "
            "survive long enough to be rescued."
        ),
    },
    {
        "isbn": "9781101875322",
        "title": "Designing Your Life",
        "author": "Bill Burnett, Dave Evans",
        "category": "Productivity",
        "price": Decimal("24.99"),
        "stock_quantity": 12,
        "publisher": "Knopf",
        "publication_date": date(2016, 9, 20),
        "description": (
            "Apply design thinking to career and life decisions, with "
            "exercises for prototyping possible futures."
        ),
    },
]

#: username, email, first name, last name, is_staff, is_superuser, provider
DEMO_USERS = [
    ("demo.admin", "admin@bookstore.test", "Ava", "Admin", True, True, "password"),
    ("demo.manager", "manager@bookstore.test", "Miles", "Manager", True, False, "password"),
    ("demo.alice", "alice.johnson@example.com", "Alice", "Johnson", False, False, "password"),
    ("demo.bob", "bob.smith@example.com", "Bob", "Smith", False, False, "google.com"),
    ("demo.carol", "carol.diaz@example.com", "Carol", "Diaz", False, False, "password"),
    ("demo.david", "david.chen@example.com", "David", "Chen", False, False, "google.com"),
    ("demo.eve", "eve.patel@example.com", "Eve", "Patel", False, False, "password"),
    ("demo.frank", "frank.moore@example.com", "Frank", "Moore", False, False, "password"),
    ("demo.grace", "grace.lee@example.com", "Grace", "Lee", False, False, "google.com"),
    ("demo.henry", "henry.wright@example.com", "Henry", "Wright", False, False, "password"),
]

#: rating, title, comment. Reused across books, one per reviewer.
REVIEW_TEMPLATES = [
    (5, "Excellent", "Clear, well written and genuinely useful. I keep coming back to it."),
    (4, "Very good", "Solid explanations and good examples. A couple of chapters drag a little."),
    (4, "Worth the money", "Covers more than I expected and the exercises are helpful."),
    (3, "Decent", "Good overview, but some sections assume more background than I had."),
    (5, "A favourite", "One of the few technical books I have read cover to cover."),
    (2, "Not for me", "The content is fine, but the pacing and layout did not work for me."),
    (4, "Practical", "Lots of concrete advice I could apply the same week."),
    (5, "Highly recommended", "Exactly the right depth, with references for going further."),
]

#: order number, username (None = guest), status, days ago, item indices and
#: quantities, paid?, cancelled?
DEMO_ORDERS = [
    ("0001", "demo.alice", Order.STATUS_DELIVERED, 32, [(0, 1), (7, 1)], True, False),
    ("0002", "demo.alice", Order.STATUS_DELIVERED, 18, [(4, 1)], True, False),
    ("0003", "demo.bob", Order.STATUS_SHIPPED, 6, [(2, 1), (13, 1)], True, False),
    ("0004", "demo.bob", Order.STATUS_PROCESSING, 3, [(8, 1)], True, False),
    ("0005", "demo.carol", Order.STATUS_CONFIRMED, 2, [(1, 1), (9, 1), (16, 1)], True, False),
    ("0006", "demo.carol", Order.STATUS_PENDING, 1, [(11, 1)], False, False),
    ("0007", "demo.david", Order.STATUS_DELIVERED, 25, [(5, 1), (12, 1)], True, False),
    ("0008", "demo.david", Order.STATUS_CANCELLED, 10, [(3, 1)], True, True),
    ("0009", "demo.eve", Order.STATUS_DELIVERED, 14, [(6, 1)], True, False),
    ("0010", "demo.eve", Order.STATUS_CONFIRMED, 1, [(10, 2), (19, 1)], True, False),
    ("0011", "demo.frank", Order.STATUS_CANCELLED, 7, [(15, 1), (18, 1)], False, True),
    ("0012", "demo.grace", Order.STATUS_SHIPPED, 4, [(17, 1)], True, False),
    ("0013", None, Order.STATUS_CONFIRMED, 5, [(20, 1)], True, False),
    ("0014", "demo.henry", Order.STATUS_PENDING, 0, [(14, 1), (21, 1)], False, False),
]

CANCELLATION_REASONS = [
    "Customer changed their mind.",
    "Duplicate order placed by mistake.",
]


class Command(BaseCommand):
    help = "Create or refresh the demo store dataset (safe to re-run)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=DEMO_PASSWORD,
            help=(
                "Password for the demo accounts, used only by the Django "
                f"admin. Defaults to {DEMO_PASSWORD}."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"]
        now = timezone.now()

        self.stdout.write("Seeding the book catalogue...")
        call_command("seed_books")
        books = self._seed_extra_books()

        self.stdout.write("Seeding demo accounts...")
        users = self._seed_users(password)
        self._seed_identities(users, now)

        self.stdout.write("Seeding reviews...")
        review_count = self._seed_reviews(books, users, now)

        self.stdout.write("Seeding carts...")
        cart_count = self._seed_carts(books, users)

        self.stdout.write("Seeding orders and payments...")
        order_count, payment_count = self._seed_orders(books, users, now)

        self.stdout.write(
            self.style.SUCCESS(
                "Demo data ready: "
                f"{Book.objects.count()} books, "
                f"{len(users)} demo accounts, "
                f"{review_count} reviews, "
                f"{cart_count} carts, "
                f"{order_count} new orders, "
                f"{payment_count} payments."
            )
        )
        self.stdout.write(
            f"Demo accounts use the password {password!r} for /admin/."
        )

    # -- catalogue ---------------------------------------------------------

    def _seed_extra_books(self):
        for book_data in EXTRA_BOOKS:
            data = dict(book_data)
            isbn = data.pop("isbn")
            Book.objects.update_or_create(isbn=isbn, defaults=data)

        return {book.isbn: book for book in Book.objects.all()}

    # -- accounts ----------------------------------------------------------

    def _seed_users(self, password):
        User = get_user_model()
        users = {}

        for username, email, first, last, is_staff, is_superuser, _ in DEMO_USERS:
            user, _created = User.objects.update_or_create(
                username=username,
                defaults={
                    "email": email,
                    "first_name": first,
                    "last_name": last,
                    "is_staff": is_staff,
                    "is_superuser": is_superuser,
                    "is_active": True,
                },
            )
            user.set_password(password)
            user.save(update_fields=["password"])
            users[username] = user

        return users

    def _seed_identities(self, users, now):
        for index, (username, email, first, last, _staff, _super, provider) in enumerate(
            DEMO_USERS, start=1
        ):
            FirebaseIdentity.objects.update_or_create(
                uid=f"demo-uid-{index:04d}",
                defaults={
                    "user": users[username],
                    "provider": provider,
                    "email": email,
                    "email_verified": True,
                    "display_name": f"{first} {last}",
                    "last_login_at": now - timedelta(days=index, hours=index),
                },
            )

    # -- reviews -----------------------------------------------------------

    def _seed_reviews(self, books, users, now):
        reviewers = [
            users["demo.alice"],
            users["demo.bob"],
            users["demo.carol"],
            users["demo.david"],
            users["demo.eve"],
            users["demo.grace"],
        ]
        # Every third book gets reviews, so the catalogue has both reviewed
        # and brand-new titles.
        target_books = list(books.values())[::2][:10]
        created = 0

        for book_index, book in enumerate(target_books):
            for offset, user in enumerate(reviewers):
                rating, title, comment = REVIEW_TEMPLATES[
                    (book_index + offset) % len(REVIEW_TEMPLATES)
                ]
                review, was_created = Review.objects.update_or_create(
                    book=book,
                    user=user,
                    defaults={
                        "rating": rating,
                        "title": title,
                        "comment": comment,
                    },
                )
                if was_created:
                    created += 1

                Review.objects.filter(pk=review.pk).update(
                    created_at=now - timedelta(days=(book_index * 3 + offset)),
                    updated_at=now - timedelta(days=(book_index * 3 + offset)),
                )

        return created

    # -- carts -------------------------------------------------------------

    def _seed_carts(self, books, users):
        catalogue = list(books.values())
        plans = {
            "demo.alice": [(0, 1), (5, 2)],
            "demo.bob": [(2, 1)],
            "demo.carol": [(9, 1), (12, 1), (16, 1)],
            "demo.eve": [(7, 2)],
        }
        created = 0

        for username, items in plans.items():
            cart, was_created = Cart.objects.update_or_create(
                session_key=f"seed-demo-cart-{username}",
                defaults={"user": users[username]},
            )
            if was_created:
                created += 1

            # Reset the contents so a re-run does not accumulate rows.
            cart.items.all().delete()
            for book_index, quantity in items:
                CartItem.objects.create(
                    cart=cart,
                    book=catalogue[book_index],
                    quantity=quantity,
                )

        return created

    # -- orders ------------------------------------------------------------

    def _seed_orders(self, books, users, now):
        catalogue = list(books.values())
        created_orders = 0
        created_payments = 0

        for number, username, status, days_ago, items, paid, cancelled in DEMO_ORDERS:
            session_key = f"{ORDER_MARKER}{number}"
            if Order.objects.filter(session_key=session_key).exists():
                # Already seeded in an earlier run; leave it alone so the
                # stock reservation is not applied twice.
                continue

            order = Order.objects.create(
                user=users[username] if username else None,
                session_key=session_key,
                status=status,
                total_amount=Decimal("0.00"),
                stock_reserved=paid and not cancelled,
            )

            total = Decimal("0.00")
            for book_index, quantity in items:
                book = catalogue[book_index]
                OrderItem.objects.create(
                    order=order,
                    book=book,
                    book_title=book.title,
                    unit_price=book.price,
                    quantity=quantity,
                )
                total += book.price * quantity

                if order.stock_reserved:
                    # One sample title is deliberately out of stock, and a
                    # demo order must not push any count negative.
                    Book.objects.filter(
                        pk=book.pk, stock_quantity__gte=quantity
                    ).update(stock_quantity=F("stock_quantity") - quantity)

            total = total.quantize(Decimal("0.01"))
            placed_at = now - timedelta(days=days_ago)
            paid_at = placed_at + timedelta(hours=2) if paid else None
            cancelled_at = (
                placed_at + timedelta(days=1) if cancelled else None
            )

            order.total_amount = total
            order.paid_at = paid_at
            order.cancelled_at = cancelled_at
            order.cancellation_reason = (
                CANCELLATION_REASONS[int(number) % len(CANCELLATION_REASONS)]
                if cancelled
                else ""
            )
            order.save(
                update_fields=[
                    "total_amount",
                    "paid_at",
                    "cancelled_at",
                    "cancellation_reason",
                ]
            )
            # auto_now_add/auto_now ignore explicit values, so set the
            # timeline afterwards to backdate the demo history.
            Order.objects.filter(pk=order.pk).update(
                created_at=placed_at,
                updated_at=paid_at or cancelled_at or placed_at,
            )

            if paid:
                Payment.objects.create(
                    order=order,
                    amount=total,
                    method=Payment.METHOD_CARD,
                    status=Payment.STATUS_SUCCEEDED,
                    reference=f"DEMO-PAY-{number}",
                    card_last4=str(4000 + int(number))[-4:],
                    user=order.user,
                )
                Payment.objects.filter(
                    order=order, reference=f"DEMO-PAY-{number}"
                ).update(created_at=paid_at)
                created_payments += 1
            elif status == Order.STATUS_PENDING:
                Payment.objects.create(
                    order=order,
                    amount=total,
                    method=Payment.METHOD_CARD,
                    status=Payment.STATUS_FAILED,
                    reference=f"DEMO-PAY-FAIL-{number}",
                    failure_reason="Card declined (demo data).",
                    card_last4="0002",
                    user=order.user,
                )
                Payment.objects.filter(
                    order=order, reference=f"DEMO-PAY-FAIL-{number}"
                ).update(created_at=placed_at + timedelta(minutes=5))
                created_payments += 1

            created_orders += 1

        return created_orders, created_payments

"""Order placement with availability checking (issue #8, TC-OBS-010).

Placement is all-or-nothing: every cart line must be satisfiable against
current stock before an order is created. Row locks
(``select_for_update``) keep concurrent orders from both passing the same
check.
"""

from decimal import Decimal

from django.db import transaction

from books.models import Book

from .models import Order, OrderItem


def _availability_problems(items, books):
    """Return availability problems for cart items against current stock.

    ``items`` is an iterable of cart items with ``book`` loaded;
    ``books`` maps book pk to the current ``Book`` row (may be missing if
    the book was deleted).
    """
    problems = []

    for item in items:
        book = books.get(item.book_id)

        if book is None:
            problems.append(
                {
                    "book_id": item.book_id,
                    "title": "Unknown book",
                    "requested": item.quantity,
                    "available": 0,
                    "reason": "This book is no longer in the catalogue.",
                }
            )
        elif book.stock_quantity <= 0:
            problems.append(
                {
                    "book_id": book.pk,
                    "title": book.title,
                    "requested": item.quantity,
                    "available": 0,
                    "reason": "This book is out of stock.",
                }
            )
        elif item.quantity > book.stock_quantity:
            problems.append(
                {
                    "book_id": book.pk,
                    "title": book.title,
                    "requested": item.quantity,
                    "available": book.stock_quantity,
                    "reason": (
                        "Only {available} copy(ies) of {title} left, but "
                        "{requested} were requested.".format(
                            available=book.stock_quantity,
                            title=book.title,
                            requested=item.quantity,
                        )
                    ),
                }
            )

    return problems


def check_cart_availability(cart):
    """Return a list of availability problems for the cart.

    Each problem is a dict describing one cart line that cannot be
    fulfilled right now. An empty list means the whole cart is available.
    """
    items = list(
        cart.items.select_related("book").order_by("added_at", "pk")
    )
    book_ids = {item.book_id for item in items}
    books = {book.pk: book for book in Book.objects.filter(pk__in=book_ids)}

    return _availability_problems(items, books)


def cart_order_total(cart):
    """Order total for the cart, quantized to cents."""
    total = sum(
        (item.subtotal for item in cart.items.select_related("book")),
        Decimal("0.00"),
    )
    return total.quantize(Decimal("0.01"))


@transaction.atomic
def place_order_from_cart(cart, user=None):
    """Create an ``Order`` (status PENDING) from the cart.

    Returns ``(order, problems)``. When ``problems`` is non-empty no order
    is created and the caller must reject the request.

    The order snapshots title and unit price per line. Stock is *not*
    decremented here: it is reserved when payment succeeds (issue #9), so
    a failed payment never leaves the catalogue inconsistent and the
    customer can retry payment or edit the cart.
    """
    items = list(
        cart.items.select_related("book").order_by("added_at", "pk")
    )

    if not items:
        return None, [
            {
                "book_id": None,
                "title": "Empty cart",
                "requested": 0,
                "available": 0,
                "reason": "The shopping cart is empty.",
            }
        ]

    # Lock the books referenced by the cart so availability cannot change
    # between the check and the order creation inside this transaction.
    book_ids = {item.book_id for item in items}
    books = {
        book.pk: book
        for book in Book.objects.select_for_update().filter(
            pk__in=book_ids
        )
    }

    problems = _availability_problems(items, books)
    if problems:
        return None, problems

    order = Order.objects.create(
        user=user if user is not None and user.is_authenticated else None,
        session_key=cart.session_key,
        status=Order.STATUS_PENDING,
        total_amount=cart_order_total(cart),
    )

    for item in items:
        book = books[item.book_id]
        OrderItem.objects.create(
            order=order,
            book=book,
            book_title=book.title,
            unit_price=book.price,
            quantity=item.quantity,
        )

    return order, []

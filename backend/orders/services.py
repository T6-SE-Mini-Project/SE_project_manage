"""Order placement, availability checking and cancellation.

Placement (issue #8, TC-OBS-010) is all-or-nothing: every cart line must
be satisfiable against current stock before an order is created. Row
locks (``select_for_update``) keep concurrent orders from both passing
the same check.

Cancellation (issue #10) is the mirror image: an order may only be
cancelled while it is in one of ``Order.CANCELLABLE_STATUSES``, and
cancelling an order that already reserved stock returns that stock to
the catalogue.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

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


#: Fulfilment transitions an administrator may apply (issue #12). Each key
#: lists the statuses that may follow it. Cancellation is handled by
#: ``cancel_order`` instead, because it also releases stock.
ALLOWED_STATUS_TRANSITIONS = {
    Order.STATUS_CONFIRMED: {Order.STATUS_PROCESSING},
    Order.STATUS_PROCESSING: {Order.STATUS_SHIPPED},
    Order.STATUS_SHIPPED: {Order.STATUS_DELIVERED},
}


def release_order_stock(order):
    """Return the stock reserved by ``order`` to the catalogue.

    Does nothing when the order holds no reservation, so calling it twice
    cannot inflate stock. Must run inside a transaction.
    """
    if not order.stock_reserved:
        return False

    for item in order.items.all():
        Book.objects.filter(pk=item.book_id).update(
            stock_quantity=F("stock_quantity") + item.quantity
        )

    order.stock_reserved = False
    return True


@transaction.atomic
def cancel_order(order, reason="", by_staff=False):
    """Cancel ``order`` when it satisfies the cancellation conditions.

    Returns ``(order, error)``. ``error`` is a message when the order
    cannot be cancelled, in which case nothing is changed. Paid orders
    release their reserved stock on cancellation and are reported with
    ``refund_due`` set.
    """
    # Lock the order so two cancellation requests cannot both pass the
    # eligibility check and release the stock twice.
    order = Order.objects.select_for_update().get(pk=order.pk)

    if order.is_cancelled:
        return None, "This order has already been cancelled."

    if not order.is_cancellable:
        return None, (
            "This order can no longer be cancelled because it has already "
            f"been {order.get_status_display().lower()}."
        )

    release_order_stock(order)

    order.status = Order.STATUS_CANCELLED
    order.cancelled_at = timezone.now()
    order.cancellation_reason = (
        reason.strip()[:255]
        or ("Cancelled by an administrator." if by_staff else "Cancelled by the customer.")
    )
    order.save(
        update_fields=[
            "status",
            "cancelled_at",
            "cancellation_reason",
            "stock_reserved",
            "updated_at",
        ]
    )

    return order, None


@transaction.atomic
def update_order_status(order, new_status):
    """Advance ``order`` to ``new_status`` (administrator fulfilment).

    Returns ``(order, error)``. Only the transitions in
    ``ALLOWED_STATUS_TRANSITIONS`` are accepted, so an order cannot skip
    fulfilment steps or move backwards.
    """
    order = Order.objects.select_for_update().get(pk=order.pk)

    valid_statuses = {choice for choice, _ in Order.STATUS_CHOICES}
    if new_status not in valid_statuses:
        return None, f"{new_status!r} is not a valid order status."

    if new_status == Order.STATUS_CANCELLED:
        return None, (
            "Use the cancellation operation to cancel an order so that "
            "reserved stock is released."
        )

    allowed = ALLOWED_STATUS_TRANSITIONS.get(order.status, set())

    if new_status not in allowed:
        return None, (
            "An order with status "
            f"{order.get_status_display().lower()} cannot be changed to "
            f"{dict(Order.STATUS_CHOICES)[new_status].lower()}."
        )

    order.status = new_status
    order.save(update_fields=["status", "updated_at"])

    return order, None


@transaction.atomic
def claim_session_orders(previous_session_key, new_session_key, user):
    """Attach orders placed as a guest to the customer who just signed in.

    ``django.contrib.auth.login()`` cycles the session key, and guest
    orders are keyed by it, so without this an order placed just before
    logging in would disappear from the customer's history (issue #10).

    Only orders that have no owner are claimed, so one customer can never
    take over another customer's order. Returns the number of orders
    claimed.
    """
    if not previous_session_key or user is None or not user.is_authenticated:
        return 0

    return Order.objects.filter(
        session_key=previous_session_key,
        user__isnull=True,
    ).update(
        user=user,
        session_key=new_session_key or previous_session_key,
    )

"""Payment processing and order confirmation (issue #9, TC-OBS-012).

Flow for ``process_order_payment``:

1. The order must be ``PENDING`` (a confirmed order cannot be paid
   again).
2. The card details are validated (format-level checks only; the full
   number is never stored).
3. Availability is re-checked inside the transaction with row locks on
   the ordered books. If stock no longer covers an order line, the
   attempt is recorded as a failed payment and nothing is charged.
4. The gateway charge is attempted. On success the books' stock is
   decremented atomically, the order becomes ``CONFIRMED`` and the
   customer's cart is emptied. On failure only the failed-payment record
   is written; the order stays ``PENDING`` and stock and cart are
   untouched, so the payment can be retried.

The function returns a :class:`PaymentOutcome` instead of raising for
payment outcomes: because the whole attempt runs in one transaction,
raising would roll back the failed-payment record that must be kept for
the order history. Only programming errors raise.
"""

from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from books.models import Book
from cart.models import Cart
from orders.models import Order

from .gateways import gateway
from .models import Payment


@dataclass
class PaymentOutcome:
    """Result of one payment attempt.

    ``error`` is empty when the payment succeeded. ``status`` suggests
    the HTTP status code for the API layer.
    """

    payment: Payment | None = None
    error: str = ""
    status: int = 200
    availability: list = field(default_factory=list)

    @property
    def succeeded(self):
        return not self.error


def _normalize_card_number(raw):
    return str(raw).replace(" ", "").replace("-", "")


def _luhn_valid(number):
    digits = [int(d) for d in number]
    checksum = 0

    for index, digit in enumerate(reversed(digits)):
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit

    return checksum % 10 == 0


def validate_card_details(data):
    """Return ``(card_number, cvc, month, year)`` or an error message."""
    card_number = _normalize_card_number(data.get("card_number", ""))
    cvc = str(data.get("cvc", "")).strip()
    expiry_month = data.get("expiry_month")
    expiry_year = data.get("expiry_year")

    if not card_number.isdigit() or not 13 <= len(card_number) <= 19:
        return None, "Card number must be 13 to 19 digits."

    if not _luhn_valid(card_number):
        return None, "Card number is not valid."

    if not cvc.isdigit() or not 3 <= len(cvc) <= 4:
        return None, "CVC must be 3 or 4 digits."

    try:
        month = int(expiry_month)
        year = int(expiry_year)
    except (TypeError, ValueError):
        return None, "Expiry month and year must be numbers."

    if not 1 <= month <= 12:
        return None, "Expiry month must be between 1 and 12."

    today = timezone.localdate()
    if year < today.year or (year == today.year and month < today.month):
        return None, "The card has expired."

    return (card_number, cvc, month, year), None


def _payment_user(user):
    return user if user is not None and user.is_authenticated else None


def _stock_problems(order, books):
    problems = []

    for item in order.items.select_related("book"):
        book = books.get(item.book_id)
        available = book.stock_quantity if book is not None else 0

        if available < item.quantity:
            problems.append(
                {
                    "book_id": item.book_id,
                    "title": item.book_title,
                    "requested": item.quantity,
                    "available": available,
                    "reason": (
                        "Only {available} copy(ies) of {title} left, but "
                        "{requested} are on the order.".format(
                            available=available,
                            title=item.book_title,
                            requested=item.quantity,
                        )
                    ),
                }
            )

    return problems


def _record_payment(order, status, card_number, user, **extra):
    return Payment.objects.create(
        order=order,
        amount=order.total_amount,
        status=status,
        card_last4=card_number[-4:],
        user=_payment_user(user),
        **extra,
    )


@transaction.atomic
def process_order_payment(order, card_data, user=None):
    """Attempt payment for ``order``; confirm it on success.

    Always returns a :class:`PaymentOutcome` describing what happened;
    failed attempts are recorded as ``Payment`` rows.
    """
    # Lock the order row so concurrent payment attempts serialize: the
    # second attempt sees the updated status instead of double-charging.
    order = Order.objects.select_for_update().get(pk=order.pk)

    if not order.is_payable:
        return PaymentOutcome(
            error=(
                "This order has already been confirmed and cannot be "
                "paid again."
            ),
            status=409,
        )

    card, card_error = validate_card_details(card_data)
    if card_error:
        return PaymentOutcome(error=card_error, status=400)

    card_number, cvc, month, year = card

    book_ids = list(order.items.values_list("book_id", flat=True))
    books = {
        book.pk: book
        for book in Book.objects.select_for_update().filter(
            pk__in=book_ids
        )
    }

    problems = _stock_problems(order, books)
    if problems:
        payment = _record_payment(
            order,
            Payment.STATUS_FAILED,
            card_number,
            user,
            failure_reason=(
                "The order can no longer be fulfilled: books became "
                "unavailable."
            ),
        )
        return PaymentOutcome(
            payment=payment,
            error=(
                "Your order can no longer be fulfilled because some "
                "books are not available in the ordered quantity."
            ),
            status=409,
            availability=problems,
        )

    result = gateway.charge(
        order.total_amount,
        card_number,
        cvc,
        month,
        year,
    )

    if not result.succeeded:
        payment = _record_payment(
            order,
            Payment.STATUS_FAILED,
            card_number,
            user,
            failure_reason=result.failure_reason,
        )
        return PaymentOutcome(
            payment=payment,
            error=result.failure_reason,
            status=402,
        )

    # Reserve the stock and confirm the order.
    for item in order.items.all():
        Book.objects.filter(pk=item.book_id).update(
            stock_quantity=F("stock_quantity") - item.quantity
        )

    order.status = Order.STATUS_CONFIRMED
    order.save(update_fields=["status", "updated_at"])

    payment = _record_payment(
        order,
        Payment.STATUS_SUCCEEDED,
        card_number,
        user,
        reference=result.reference,
    )

    # The purchase is complete: empty the customer's cart.
    Cart.objects.filter(session_key=order.session_key).delete()

    return PaymentOutcome(payment=payment)

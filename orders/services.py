from decimal import Decimal

from django.db import transaction

from books.models import Book
from cart.services import get_cart

from .models import BillingAddress, Order, OrderItem


class CheckoutError(Exception):
    def __init__(self, message, status=400, errors=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.errors = errors


def _resolve_billing_address(form, user, save_address):
    address = form.save(commit=False)

    if user is not None and user.is_authenticated and save_address:
        address.user = user
        existing = BillingAddress.objects.filter(
            user=user,
            fingerprint=address.calculate_fingerprint(),
        ).first()

        if existing is not None:
            return existing, True

        address.save()
        return address, True

    # Guests, and customers who clear "Save this address", get an order
    # snapshot that is not added to the customer's saved address book.
    address.user = None
    address.save()
    return address, False


def place_order(request, form, save_address=False):
    """Create an order from the current cart and a validated address form.

    PAYMENT INTEGRATION POINT
    -------------------------
    This project has no payment gateway yet, so the order is deliberately
    created with ``pending_payment`` status. A future payment milestone should
    collect payment through the provider's hosted/secure fields, then update
    this order status after the provider confirms payment. Card numbers, CVVs
    and banking credentials must never be stored in these models.
    """
    cart = get_cart(request)
    cart_items = list(
        cart.items.select_related("book").order_by("added_at", "pk")
    )

    if not cart_items:
        raise CheckoutError(
            "Your cart is empty. Add a book before checking out."
        )

    with transaction.atomic():
        book_ids = [item.book_id for item in cart_items]
        locked_books = Book.objects.select_for_update().in_bulk(book_ids)

        for item in cart_items:
            book = locked_books.get(item.book_id)
            if book is None:
                raise CheckoutError(
                    f"{item.book.title} is no longer available.",
                    status=409,
                )
            if item.quantity > book.stock_quantity:
                raise CheckoutError(
                    (
                        f"Only {book.stock_quantity} copies of "
                        f"{book.title} are available."
                    ),
                    status=409,
                )

        address, address_saved = _resolve_billing_address(
            form,
            request.user,
            save_address,
        )

        total = sum(
            (
                (locked_books[item.book_id].price * item.quantity)
                for item in cart_items
            ),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))

        order = Order.objects.create(
            user=(
                request.user
                if request.user.is_authenticated
                else None
            ),
            session_key=request.session.session_key or "",
            billing_address=address,
            total=total,
        )

        for item in cart_items:
            book = locked_books[item.book_id]
            OrderItem.objects.create(
                order=order,
                book=book,
                title=book.title,
                unit_price=book.price,
                quantity=item.quantity,
            )

            book.stock_quantity -= item.quantity
            book.save(update_fields=["stock_quantity", "updated_at"])

        cart.items.all().delete()

    return order, address_saved

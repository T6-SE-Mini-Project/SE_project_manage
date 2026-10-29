import json

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import (
    require_GET,
    require_POST,
    require_http_methods,
)

from books.models import Book
from config.cache import (
    BOOKS,
    CART,
    PER_CALLER,
    TTL_CART,
    cached_json,
    invalidate,
)

from .models import CartItem
from .serializers import serialize_cart
from .services import get_cart


def _cart_response(cart):
    return JsonResponse({"cart": serialize_cart(cart)})


def _changed_cart_response(cart):
    """Respond to a write, and drop the cached cart reads it invalidates."""
    invalidate(CART)
    return _cart_response(cart)


def _read_json(request):
    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, JsonResponse(
            {"error": "Invalid JSON body."},
            status=400,
        )

    if not isinstance(data, dict):
        return None, JsonResponse(
            {"error": "JSON body must be an object."},
            status=400,
        )

    return data, None


def _parse_positive_integer(value, field_name, default=None):
    if value is None:
        if default is None:
            return None, f"{field_name} is required."
        return default, None

    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None, f"{field_name} must be a positive integer."

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, f"{field_name} must be a positive integer."

    if parsed < 1:
        return None, f"{field_name} must be at least 1."

    return parsed, None


# BOOKS as well as CART: every line carries its book's price and stock.
@require_GET
@cached_json(TTL_CART, namespaces=[CART, BOOKS], scope=PER_CALLER)
def cart_detail(request):
    cart = get_cart(request)
    return _cart_response(cart)


@require_POST
@transaction.atomic
def cart_item_add(request):
    data, error_response = _read_json(request)
    if error_response is not None:
        return error_response

    book_id, error = _parse_positive_integer(
        data.get("book_id"),
        "book_id",
    )
    if error is not None:
        return JsonResponse({"error": error}, status=400)

    quantity, error = _parse_positive_integer(
        data.get("quantity"),
        "quantity",
        default=1,
    )
    if error is not None:
        return JsonResponse({"error": error}, status=400)

    book = Book.objects.filter(pk=book_id).first()
    if book is None:
        return JsonResponse({"error": "Book not found."}, status=404)

    if not book.in_stock:
        return JsonResponse(
            {"error": "This book is out of stock."},
            status=400,
        )

    cart = get_cart(request)
    item = CartItem.objects.filter(cart=cart, book=book).first()
    new_quantity = quantity + (item.quantity if item else 0)

    if new_quantity > book.stock_quantity:
        return JsonResponse(
            {
                "error": (
                    "Requested quantity exceeds available stock "
                    f"({book.stock_quantity})."
                )
            },
            status=400,
        )

    if item is None:
        CartItem.objects.create(
            cart=cart,
            book=book,
            quantity=quantity,
        )
    else:
        item.quantity = new_quantity
        item.save(update_fields=["quantity", "updated_at"])

    return _changed_cart_response(cart)


@require_http_methods(["PATCH", "PUT", "DELETE"])
@transaction.atomic
def cart_item_detail(request, pk):
    cart = get_cart(request)
    item = (
        CartItem.objects.filter(cart=cart, pk=pk)
        .select_related("book")
        .first()
    )

    if item is None:
        return JsonResponse({"error": "Cart item not found."}, status=404)

    if request.method == "DELETE":
        item.delete()
        return _changed_cart_response(cart)

    data, error_response = _read_json(request)
    if error_response is not None:
        return error_response

    quantity, error = _parse_positive_integer(
        data.get("quantity"),
        "quantity",
    )
    if error is not None:
        return JsonResponse({"error": error}, status=400)

    if quantity > item.book.stock_quantity:
        return JsonResponse(
            {
                "error": (
                    "Requested quantity exceeds available stock "
                    f"({item.book.stock_quantity})."
                )
            },
            status=400,
        )

    item.quantity = quantity
    item.save(update_fields=["quantity", "updated_at"])

    return _changed_cart_response(cart)

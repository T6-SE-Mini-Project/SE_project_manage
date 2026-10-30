from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from config.cache import (
    BOOKS,
    TTL_BOOK_DETAIL,
    TTL_BOOK_LIST,
    TTL_CATEGORIES,
    cached_json,
)

from .models import Book
from .serializers import serialize_book_detail, serialize_book_summary


def _parse_decimal(request, name):
    raw = request.GET.get(name)

    if raw is None or raw.strip() == "":
        return None

    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError):
        raise ValueError(f"{name} must be a valid number.")

    if not value.is_finite() or value < 0:
        raise ValueError(f"{name} must be a non-negative number.")

    return value


def _parse_available(raw):
    if raw is None or raw.strip() == "":
        return None

    normalized = raw.strip().lower()

    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False

    raise ValueError("available must be true or false.")


@require_GET
@cached_json(TTL_BOOK_LIST, namespaces=[BOOKS])
def book_list(request):
    books = Book.objects.all()

    search_term = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    author = request.GET.get("author", "").strip()

    try:
        min_price = _parse_decimal(request, "min_price")
        max_price = _parse_decimal(request, "max_price")
        available = _parse_available(request.GET.get("available"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if (
        min_price is not None
        and max_price is not None
        and min_price > max_price
    ):
        return JsonResponse(
            {"error": "min_price cannot be greater than max_price."},
            status=400,
        )

    if search_term:
        books = books.filter(
            Q(title__icontains=search_term)
            | Q(author__icontains=search_term)
            | Q(isbn__icontains=search_term)
            | Q(description__icontains=search_term)
        )

    if category:
        books = books.filter(category__iexact=category)

    if author:
        books = books.filter(author__icontains=author)

    if min_price is not None:
        books = books.filter(price__gte=min_price)

    if max_price is not None:
        books = books.filter(price__lte=max_price)

    if available is True:
        books = books.filter(stock_quantity__gt=0)
    elif available is False:
        books = books.filter(stock_quantity=0)

    books = list(books.order_by("title", "pk"))

    return JsonResponse(
        {
            "count": len(books),
            "books": [serialize_book_summary(book) for book in books],
        }
    )


@require_GET
@cached_json(TTL_CATEGORIES, namespaces=[BOOKS])
def book_categories(request):
    categories = list(
        Book.objects.order_by("category")
        .values_list("category", flat=True)
        .distinct()
    )

    return JsonResponse({"categories": categories})


@require_GET
@cached_json(TTL_BOOK_DETAIL, namespaces=[BOOKS])
def book_detail(request, pk):
    try:
        book = Book.objects.get(pk=pk)
    except Book.DoesNotExist:
        return JsonResponse({"error": "Book not found."}, status=404)

    return JsonResponse({"book": serialize_book_detail(book)})

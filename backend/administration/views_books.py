"""Administrator catalogue management (issue #12, OBS-F-017, TC-OBS-017).

Every view in this module is wrapped in ``staff_required_api``, so an
anonymous caller gets 401 and a signed-in customer gets 403. Catalogue
writes therefore cannot be reached from a customer account even if the
frontend route is guessed.
"""

from django.db.models import Q, ProtectedError
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from books.models import Book
from books.serializers import serialize_book_detail
from config.http import json_error, read_json, staff_required_api

from .forms import BookForm


def _form_errors(form):
    return {field: list(messages) for field, messages in form.errors.items()}


def _parse_int(raw, name, default=None):
    if raw is None or str(raw).strip() == "":
        return default, None

    try:
        return int(raw), None
    except (TypeError, ValueError):
        return None, f"{name} must be a whole number."


@require_http_methods(["GET", "POST"])
@staff_required_api
def book_collection(request):
    """GET lists the catalogue for management; POST adds a book."""
    if request.method == "GET":
        return _list_books(request)

    return _create_book(request)


def _list_books(request):
    books = Book.objects.all()

    search = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()

    low_stock, error = _parse_int(request.GET.get("low_stock"), "low_stock")
    if error is not None:
        return json_error(error, 400)

    if search:
        books = books.filter(
            Q(title__icontains=search)
            | Q(author__icontains=search)
            | Q(isbn__icontains=search)
        )

    if category:
        books = books.filter(category__iexact=category)

    if low_stock is not None:
        # Restocking view: everything at or below the given threshold.
        books = books.filter(stock_quantity__lte=low_stock)

    books = list(books.order_by("title", "pk"))

    return JsonResponse(
        {
            "count": len(books),
            "books": [serialize_book_detail(book) for book in books],
        }
    )


def _create_book(request):
    data, error_response = read_json(request)
    if error_response is not None:
        return error_response

    form = BookForm(data=data)

    if not form.is_valid():
        return json_error(
            "The book could not be saved.",
            400,
            errors=_form_errors(form),
        )

    book = form.save()

    return JsonResponse(
        {"book": serialize_book_detail(book)},
        status=201,
    )


@require_http_methods(["GET", "PATCH", "PUT", "DELETE"])
@staff_required_api
def book_detail(request, pk):
    book = Book.objects.filter(pk=pk).first()

    if book is None:
        return json_error("Book not found.", 404)

    if request.method == "GET":
        return JsonResponse({"book": serialize_book_detail(book)})

    if request.method == "DELETE":
        return _delete_book(book)

    return _update_book(request, book)


def _update_book(request, book):
    data, error_response = read_json(request)
    if error_response is not None:
        return error_response

    # PATCH semantics: start from the stored values and overlay only the
    # supplied fields, so a partial update cannot blank the rest.
    current = {
        field: getattr(book, field) for field in BookForm.Meta.fields
    }
    current.update(
        {key: value for key, value in data.items() if key in current}
    )

    form = BookForm(data=current, instance=book)

    if not form.is_valid():
        return json_error(
            "The book could not be updated.",
            400,
            errors=_form_errors(form),
        )

    updated = form.save()

    return JsonResponse({"book": serialize_book_detail(updated)})


def _delete_book(book):
    try:
        book.delete()
    except ProtectedError:
        # OrderItem protects the book so order history keeps its lines.
        # Taking the book out of sale is the supported alternative.
        return json_error(
            "This book cannot be deleted because it appears on existing "
            "orders. Set its stock to 0 to withdraw it from sale instead.",
            409,
        )

    return JsonResponse({"deleted": True, "id": book.pk})

"""Book review endpoints (issue #11, OBS-F-016, TC-OBS-016).

- ``GET  /api/reviews/?book=<id>``  list a book's reviews and its rating
  summary (public).
- ``POST /api/reviews/``            submit a review (signed-in customers).
- ``PATCH  /api/reviews/<id>/``     edit your own review.
- ``DELETE /api/reviews/<id>/``     delete your own review.

A customer may hold one review per book, which keeps the average rating
meaningful; editing is offered instead of a second submission.
"""

from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from books.models import Book
from config.cache import (
    BOOKS,
    PER_CALLER,
    REVIEWS,
    TTL_REVIEWS,
    cached_json,
    invalidate,
)
from config.http import json_error, login_required_api, read_json
from config.throttle import RATE_REVIEW, throttle

from .models import Review
from .serializers import serialize_review
from .services import rating_summary, validate_review_input


def _parse_book_id(raw):
    """Return ``(book_id, error)`` for a submitted book reference."""
    if isinstance(raw, bool) or raw is None or str(raw).strip() == "":
        return None, "book_id is required."

    try:
        book_id = int(raw)
    except (TypeError, ValueError):
        return None, "book_id must be a whole number."

    if book_id < 1:
        return None, "book_id must be a positive number."

    return book_id, None


def _current_user(request):
    return request.user if request.user.is_authenticated else None


@require_http_methods(["GET", "POST"])
def review_collection(request):
    if request.method == "GET":
        return _list_reviews(request)

    return _create_review(request)


# PER_CALLER: the payload carries "can_review" and the caller's own
# review, so it is not the same answer for two customers. BOOKS is in the
# namespaces because the rating summary is derived from the book.
@cached_json(TTL_REVIEWS, namespaces=[REVIEWS, BOOKS], scope=PER_CALLER)
def _list_reviews(request):
    book_id, error = _parse_book_id(request.GET.get("book"))

    if error is not None:
        return json_error(error.replace("book_id", "book"), 400)

    book = Book.objects.filter(pk=book_id).first()
    if book is None:
        return json_error("Book not found.", 404)

    user = _current_user(request)
    reviews = list(
        Review.objects.filter(book=book).select_related("user")
    )

    own_review = next(
        (
            review
            for review in reviews
            if user is not None and review.user_id == user.pk
        ),
        None,
    )

    return JsonResponse(
        {
            "summary": rating_summary(book),
            "reviews": [
                serialize_review(review, current_user=user)
                for review in reviews
            ],
            # The frontend uses these to decide between showing the review
            # form, the customer's existing review, or a prompt to log in.
            "can_review": user is not None and own_review is None,
            "my_review": (
                serialize_review(own_review, current_user=user)
                if own_review is not None
                else None
            ),
        }
    )


@login_required_api
@throttle(RATE_REVIEW, scope="review")
def _create_review(request):
    data, error_response = read_json(request)
    if error_response is not None:
        return error_response

    book_id, error = _parse_book_id(data.get("book_id"))
    if error is not None:
        return json_error(error, 400)

    book = Book.objects.filter(pk=book_id).first()
    if book is None:
        return json_error("Book not found.", 404)

    cleaned, errors = validate_review_input(data)
    if errors:
        return json_error(
            "Your review could not be submitted.",
            400,
            errors=errors,
        )

    already_reviewed = (
        "You have already reviewed this book. Edit your existing review "
        "instead."
    )

    if Review.objects.filter(book=book, user=request.user).exists():
        return json_error(already_reviewed, 409)

    try:
        # The create runs in its own atomic block so that a lost race on
        # the unique (book, user) constraint rolls back only the failed
        # insert, leaving the surrounding transaction usable.
        with transaction.atomic():
            review = Review.objects.create(
                book=book,
                user=request.user,
                **cleaned,
            )
    except IntegrityError:
        # Two concurrent submissions from the same customer: the second
        # one loses and is told to edit the review that now exists.
        return json_error(already_reviewed, 409)

    invalidate(REVIEWS)

    return JsonResponse(
        {
            "review": serialize_review(review, current_user=request.user),
            "summary": rating_summary(book),
        },
        status=201,
    )


@require_http_methods(["PATCH", "PUT", "DELETE"])
@login_required_api
@throttle(RATE_REVIEW, scope="review")
def review_detail(request, pk):
    review = (
        Review.objects.select_related("book", "user").filter(pk=pk).first()
    )

    if review is None:
        return json_error("Review not found.", 404)

    # Customers may only touch their own review; administrators may remove
    # any review as part of moderation.
    is_owner = review.user_id == request.user.pk

    if not is_owner and not request.user.is_staff:
        return json_error("You can only change your own review.", 403)

    book = review.book

    if request.method == "DELETE":
        review.delete()
        invalidate(REVIEWS)
        return JsonResponse({"summary": rating_summary(book)})

    if not is_owner:
        return json_error("You can only edit your own review.", 403)

    data, error_response = read_json(request)
    if error_response is not None:
        return error_response

    cleaned, errors = validate_review_input(data, partial=True)
    if errors:
        return json_error(
            "Your review could not be updated.",
            400,
            errors=errors,
        )

    if not cleaned:
        return json_error("No review fields were supplied.", 400)

    for field, value in cleaned.items():
        setattr(review, field, value)

    review.save(update_fields=[*cleaned.keys(), "updated_at"])
    invalidate(REVIEWS)

    return JsonResponse(
        {
            "review": serialize_review(review, current_user=request.user),
            "summary": rating_summary(book),
        }
    )

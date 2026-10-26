"""Review validation and aggregation (issue #11)."""

from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Avg, Count

from .models import Review


def validate_review_input(data, partial=False):
    """Validate a submitted review payload.

    Returns ``(cleaned, errors)`` where ``errors`` maps a field name to a
    message. ``partial`` is used for edits, where only the supplied
    fields are validated.
    """
    cleaned = {}
    errors = {}

    if not partial or "rating" in data:
        rating = data.get("rating")

        if isinstance(rating, bool) or rating is None:
            errors["rating"] = "A rating between 1 and 5 is required."
        else:
            try:
                rating = int(rating)
            except (TypeError, ValueError):
                errors["rating"] = "The rating must be a whole number."
            else:
                if not Review.MIN_RATING <= rating <= Review.MAX_RATING:
                    errors["rating"] = (
                        f"The rating must be between {Review.MIN_RATING} "
                        f"and {Review.MAX_RATING}."
                    )
                else:
                    cleaned["rating"] = rating

    if not partial or "title" in data:
        title = str(data.get("title") or "").strip()

        if len(title) > 120:
            errors["title"] = "The title may not exceed 120 characters."
        else:
            cleaned["title"] = title

    if not partial or "comment" in data:
        comment = str(data.get("comment") or "").strip()

        if len(comment) > Review.MAX_COMMENT_LENGTH:
            errors["comment"] = (
                "The review may not exceed "
                f"{Review.MAX_COMMENT_LENGTH} characters."
            )
        else:
            cleaned["comment"] = comment

    return cleaned, errors


def rating_summary(book):
    """Return the aggregate rating for one book.

    ``average_rating`` is ``None`` when the book has no reviews yet, so
    the frontend can distinguish "unrated" from a zero score.
    """
    aggregate = Review.objects.filter(book=book).aggregate(
        average=Avg("rating"),
        total=Count("pk"),
    )

    counts = dict(
        Review.objects.filter(book=book)
        .values_list("rating")
        .annotate(total=Count("pk"))
    )

    average = aggregate["average"]

    return {
        "book_id": book.pk,
        "review_count": aggregate["total"],
        "average_rating": (
            str(
                Decimal(average).quantize(
                    Decimal("0.1"), rounding=ROUND_HALF_UP
                )
            )
            if average is not None
            else None
        ),
        "rating_counts": {
            str(score): counts.get(score, 0)
            for score in range(Review.MAX_RATING, Review.MIN_RATING - 1, -1)
        },
    }

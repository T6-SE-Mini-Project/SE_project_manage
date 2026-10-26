def serialize_review(review, current_user=None):
    """A review as shown on the book details page.

    ``is_owner`` tells the frontend whether to offer edit and delete
    controls; the server re-checks ownership on every write.
    """
    is_owner = (
        current_user is not None
        and current_user.is_authenticated
        and review.user_id == current_user.pk
    )

    return {
        "id": review.id,
        "book_id": review.book_id,
        "rating": review.rating,
        "title": review.title,
        "comment": review.comment,
        "author": review.user.username if review.user_id else "Deleted user",
        "is_owner": is_owner,
        "is_edited": review.is_edited,
        "created_at": review.created_at.isoformat(),
        "updated_at": review.updated_at.isoformat(),
    }

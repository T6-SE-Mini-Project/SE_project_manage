from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

#: Rating bounds, enforced by model validators and a database check
#: constraint. Defined at module level because a nested ``Meta`` class
#: body cannot see the enclosing class's attributes.
MIN_RATING = 1
MAX_RATING = 5
MAX_COMMENT_LENGTH = 2000


class Review(models.Model):
    """A customer's review of a book (issue #11, OBS-F-016).

    A review is always written by a signed-in customer, so reviews can be
    attributed and each customer is limited to one review per book (they
    may edit or delete their own). The rating is constrained to 1-5 both
    in the application (validators) and in the database (check
    constraint).
    """

    # Re-exported from the module constants above so callers can write
    # Review.MIN_RATING without importing them separately.
    MIN_RATING = MIN_RATING
    MAX_RATING = MAX_RATING
    MAX_COMMENT_LENGTH = MAX_COMMENT_LENGTH

    book = models.ForeignKey(
        "books.Book",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(MIN_RATING),
            MaxValueValidator(MAX_RATING),
        ],
    )
    title = models.CharField(max_length=120, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["book", "user"],
                name="unique_review_per_customer_and_book",
            ),
            models.CheckConstraint(
                condition=models.Q(rating__gte=MIN_RATING)
                & models.Q(rating__lte=MAX_RATING),
                name="review_rating_within_range",
            ),
        ]

    def __str__(self):
        return f"{self.rating}/5 for {self.book_id} by {self.user_id}"

    @property
    def is_edited(self):
        """True when the review was changed after it was first submitted."""
        return (self.updated_at - self.created_at).total_seconds() > 1

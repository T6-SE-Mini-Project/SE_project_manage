from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from .validators import normalize_isbn, validate_isbn


class Book(models.Model):
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, db_index=True)
    isbn = models.CharField(max_length=13, unique=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, db_index=True)
    price = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    cover_image_url = models.URLField(max_length=500, blank=True)
    publisher = models.CharField(max_length=255, blank=True)
    publication_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gte=0),
                name="book_price_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(stock_quantity__gte=0),
                name="book_stock_non_negative",
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def in_stock(self):
        return self.stock_quantity > 0

    def clean(self):
        super().clean()
        self.isbn = normalize_isbn(self.isbn)
        validate_isbn(self.isbn)
        if self.price is not None and self.price < Decimal("0.00"):
            raise ValidationError(
                {"price": "Price cannot be negative."}
            )

    def save(self, *args, **kwargs):
        self.isbn = normalize_isbn(self.isbn)
        super().save(*args, **kwargs)

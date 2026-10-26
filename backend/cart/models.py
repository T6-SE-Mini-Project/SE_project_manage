from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Cart(models.Model):
    session_key = models.CharField(max_length=40, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="carts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart {self.session_key}"

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def total(self):
        total = sum(
            (item.subtotal for item in self.items.all()),
            Decimal("0.00"),
        )
        return total.quantize(Decimal("0.01"))


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )
    book = models.ForeignKey(
        "books.Book",
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["added_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "book"],
                name="unique_cart_book",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name="cart_item_quantity_positive",
            ),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.book.title}"

    @property
    def subtotal(self):
        return (self.book.price * self.quantity).quantize(Decimal("0.01"))

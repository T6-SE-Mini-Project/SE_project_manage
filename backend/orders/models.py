from decimal import Decimal

from django.conf import settings
from django.db import models


class Order(models.Model):
    """A customer order placed from a shopping cart.

    Lifecycle (issue #8 / #9):

    - ``PENDING``  — the order was placed and passed the availability
      check, but payment has not succeeded yet.
    - ``CONFIRMED`` — payment succeeded (issue #9); stock is reserved and
      the order is confirmed.
    - ``FAILED``   — payment failed; the order stays recorded for the
      customer's history but is never treated as successful.
    """

    STATUS_PENDING = "PENDING"
    STATUS_CONFIRMED = "CONFIRMED"
    STATUS_FAILED = "FAILED"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending payment"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_FAILED, "Payment failed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )
    session_key = models.CharField(max_length=40, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total_amount__gte=0),
                name="order_total_non_negative",
            ),
        ]

    def __str__(self):
        return f"Order {self.pk} ({self.status})"

    @property
    def is_confirmed(self):
        return self.status == self.STATUS_CONFIRMED

    @property
    def is_payable(self):
        """Only pending orders can receive a payment attempt."""
        return self.status == self.STATUS_PENDING


class OrderItem(models.Model):
    """A line item on an order.

    ``book_title`` and ``unit_price`` are snapshotted at placement time so
    order history stays accurate even if the catalogue changes later.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    book = models.ForeignKey(
        "books.Book",
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    book_title = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=9, decimal_places=2)
    quantity = models.PositiveIntegerField()

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name="order_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="order_item_price_non_negative",
            ),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.book_title}"

    @property
    def line_total(self):
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))

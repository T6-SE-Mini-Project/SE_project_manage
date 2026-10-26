from decimal import Decimal

from django.conf import settings
from django.db import models


class Order(models.Model):
    """A customer order placed from a shopping cart.

    Lifecycle (issues #8, #9, #10 and #12):

    - ``PENDING``    — placed and past the availability check, but not
      paid yet. A failed payment attempt leaves the order pending so the
      customer can retry.
    - ``CONFIRMED``  — payment succeeded; stock is reserved.
    - ``PROCESSING`` — an administrator started preparing the order.
    - ``SHIPPED``    — dispatched to the customer.
    - ``DELIVERED``  — the final successful state.
    - ``CANCELLED``  — cancelled by the customer (issue #10) or by an
      administrator (issue #12). Reserved stock is returned to the
      catalogue when an order is cancelled.

    Only ``PENDING``, ``CONFIRMED`` and ``PROCESSING`` orders can be
    cancelled: once an order has shipped, cancellation is no longer a
    customer-side operation.
    """

    STATUS_PENDING = "PENDING"
    STATUS_CONFIRMED = "CONFIRMED"
    STATUS_PROCESSING = "PROCESSING"
    STATUS_SHIPPED = "SHIPPED"
    STATUS_DELIVERED = "DELIVERED"
    STATUS_CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending payment"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_SHIPPED, "Shipped"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    #: Statuses a customer or administrator may still cancel from.
    CANCELLABLE_STATUSES = frozenset(
        {STATUS_PENDING, STATUS_CONFIRMED, STATUS_PROCESSING}
    )

    #: Statuses that count as revenue in the sales report (issue #24).
    REVENUE_STATUSES = frozenset(
        {
            STATUS_CONFIRMED,
            STATUS_PROCESSING,
            STATUS_SHIPPED,
            STATUS_DELIVERED,
        }
    )

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
    # Set when a payment succeeds, so order history can show when the
    # order was paid and cancellation can tell whether a refund is owed.
    paid_at = models.DateTimeField(blank=True, null=True)
    # True while this order holds catalogue stock. Stock is reserved on
    # successful payment and released on cancellation; the flag makes the
    # release happen exactly once.
    stock_reserved = models.BooleanField(default=False)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancellation_reason = models.CharField(max_length=255, blank=True)
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
        """True once payment succeeded, including later fulfilment states."""
        return self.status in {
            self.STATUS_CONFIRMED,
            self.STATUS_PROCESSING,
            self.STATUS_SHIPPED,
            self.STATUS_DELIVERED,
        }

    @property
    def is_payable(self):
        """Only pending orders can receive a payment attempt."""
        return self.status == self.STATUS_PENDING

    @property
    def is_cancelled(self):
        return self.status == self.STATUS_CANCELLED

    @property
    def is_paid(self):
        return self.paid_at is not None

    @property
    def is_cancellable(self):
        """Whether this order still satisfies the cancellation conditions."""
        return self.status in self.CANCELLABLE_STATUSES

    @property
    def refund_due(self):
        """A cancelled order that was already paid needs a refund."""
        return self.is_cancelled and self.is_paid

    @property
    def status_display(self):
        return self.get_status_display()


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

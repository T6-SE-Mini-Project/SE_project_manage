from django.conf import settings
from django.db import models


class Payment(models.Model):
    """One payment attempt against an order (issue #9, OBS-F-013).

    A new ``Payment`` row is recorded for every attempt so the payment
    history of an order shows retries. Only non-sensitive data is stored:
    the full card number is never persisted, only its last four digits.
    """

    STATUS_SUCCEEDED = "SUCCEEDED"
    STATUS_FAILED = "FAILED"

    STATUS_CHOICES = [
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
    ]

    METHOD_CARD = "CARD"

    METHOD_CHOICES = [
        (METHOD_CARD, "Card"),
    ]

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(
        max_length=20,
        choices=METHOD_CHOICES,
        default=METHOD_CARD,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        db_index=True,
    )
    reference = models.CharField(max_length=64, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    card_last4 = models.CharField(max_length=4, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name="payment_amount_non_negative",
            ),
        ]

    def __str__(self):
        return f"Payment {self.pk} for order {self.order_id} ({self.status})"

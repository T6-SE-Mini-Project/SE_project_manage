import hashlib
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models

PHONE_NUMBER_VALIDATOR = RegexValidator(
    r"^\d{10}$",
    "Phone number must be exactly 10 digits.",
)

PIN_CODE_VALIDATOR = RegexValidator(
    r"^\d{6}$",
    "PIN code must be exactly 6 digits.",
)


class BillingAddress(models.Model):
    """A billing address saved by a customer or attached to an order.

    Authenticated customers can keep reusable addresses. Guest checkout
    addresses are stored as order snapshots and have no user attached.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="billing_addresses",
    )
    full_name = models.CharField(max_length=150)
    phone_number = models.CharField(
        max_length=10,
        validators=[PHONE_NUMBER_VALIDATOR],
    )
    email = models.EmailField()
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(
        max_length=6,
        validators=[PIN_CODE_VALIDATOR],
    )
    country = models.CharField(max_length=100, default="India")
    fingerprint = models.CharField(max_length=64, editable=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-pk"]
        indexes = [
            models.Index(
                fields=["user", "fingerprint"],
                name="billing_user_fingerprint_idx",
            ),
        ]

    def __str__(self):
        return f"{self.full_name}, {self.city} {self.postal_code}"

    def normalized_values(self):
        return {
            "full_name": " ".join(self.full_name.split()),
            "phone_number": (self.phone_number or "").strip(),
            "email": (self.email or "").strip().lower(),
            "address_line1": " ".join((self.address_line1 or "").split()),
            "address_line2": " ".join((self.address_line2 or "").split()),
            "city": " ".join((self.city or "").split()),
            "state": " ".join((self.state or "").split()),
            "postal_code": (self.postal_code or "").strip(),
            "country": " ".join((self.country or "India").split()),
        }

    def calculate_fingerprint(self):
        values = self.normalized_values()
        payload = "|".join(
            values[field].lower()
            for field in (
                "full_name",
                "phone_number",
                "email",
                "address_line1",
                "address_line2",
                "city",
                "state",
                "postal_code",
                "country",
            )
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def save(self, *args, **kwargs):
        for field, value in self.normalized_values().items():
            setattr(self, field, value)

        self.fingerprint = self.calculate_fingerprint()
        super().save(*args, **kwargs)


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "Awaiting payment integration"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"

    reference = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    billing_address = models.ForeignKey(
        BillingAddress,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING_PAYMENT,
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"Order {self.reference}"

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def short_reference(self):
        return str(self.reference).split("-")[0].upper()


class OrderItem(models.Model):
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
    title = models.CharField(max_length=255)
    unit_price = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "book"],
                name="unique_order_book",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name="order_item_quantity_positive",
            ),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.title}"

    @property
    def subtotal(self):
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))

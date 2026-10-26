from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "amount",
        "method",
        "status",
        "reference",
        "card_last4",
        "created_at",
    )
    list_filter = ("status", "method", "created_at")
    search_fields = ("reference", "order__session_key")
    readonly_fields = (
        "order",
        "amount",
        "method",
        "status",
        "reference",
        "failure_reason",
        "card_last4",
        "user",
        "created_at",
    )

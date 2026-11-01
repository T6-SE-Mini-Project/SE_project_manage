from django.contrib import admin

from .models import BillingAddress, Order, OrderItem


@admin.register(BillingAddress)
class BillingAddressAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "city",
        "state",
        "postal_code",
        "country",
        "user",
        "updated_at",
    )
    list_filter = ("country", "state")
    search_fields = (
        "full_name",
        "email",
        "phone_number",
        "postal_code",
    )
    readonly_fields = ("fingerprint", "created_at", "updated_at")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("title", "unit_price", "quantity")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "short_reference",
        "user",
        "status",
        "total",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("reference", "user__username", "session_key")
    list_select_related = ("user", "billing_address")
    readonly_fields = (
        "reference",
        "billing_address",
        "total",
        "created_at",
        "updated_at",
    )
    inlines = [OrderItemInline]

from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("book", "book_title", "unit_price", "quantity")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "session_key",
        "status",
        "total_amount",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("session_key", "user__username")
    readonly_fields = (
        "session_key",
        "user",
        "status",
        "total_amount",
        "created_at",
        "updated_at",
    )
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "book",
        "book_title",
        "unit_price",
        "quantity",
    )
    list_select_related = ("order", "book")

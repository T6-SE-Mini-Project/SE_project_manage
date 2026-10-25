from django.contrib import admin

from .models import Cart, CartItem


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "session_key", "user", "updated_at")
    search_fields = ("session_key",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "cart", "book", "quantity", "updated_at")
    list_select_related = ("cart", "book")
    readonly_fields = ("added_at", "updated_at")

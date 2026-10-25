from django.contrib import admin

from .models import Book


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "author",
        "isbn",
        "category",
        "price",
        "stock_quantity",
        "in_stock",
    )
    list_filter = ("category",)
    search_fields = ("title", "author", "isbn")
    ordering = ("title", "pk")
    readonly_fields = ("created_at", "updated_at")

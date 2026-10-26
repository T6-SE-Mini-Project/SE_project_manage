from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "book", "user", "rating", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("book__title", "user__username", "title", "comment")
    list_select_related = ("book", "user")
    readonly_fields = ("created_at", "updated_at")

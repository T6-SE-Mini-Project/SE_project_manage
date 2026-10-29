from django.contrib import admin

from .models import FirebaseIdentity


@admin.register(FirebaseIdentity)
class FirebaseIdentityAdmin(admin.ModelAdmin):
    """Read-only view of who signed in with which Firebase account.

    Nothing here is editable: Firebase is the source of truth for all of
    it, and every field is rewritten from the verified ID token on the
    customer's next sign-in. Promoting a customer to administrator is
    done on their Django user (``is_staff``), not here.
    """

    list_display = ["uid", "user", "email", "provider", "last_login_at"]
    list_filter = ["provider", "email_verified"]
    search_fields = ["uid", "email", "user__username", "user__email"]
    readonly_fields = [
        "user",
        "uid",
        "provider",
        "email",
        "email_verified",
        "display_name",
        "created_at",
        "last_login_at",
    ]

    def has_add_permission(self, request):
        return False

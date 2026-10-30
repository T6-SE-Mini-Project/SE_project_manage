"""The link between a Firebase account and a Django user.

Firebase owns credentials — passwords, Google sign-in, password resets —
and identifies every customer by an immutable ``uid``. Everything else in
this project (orders, carts, reviews, ``is_staff``) is keyed by a Django
user, so each Firebase uid is recorded here against exactly one user.

The uid, not the email address, is the identity: a customer can change
their email in Firebase, and two providers can report the same address,
but the uid never changes.
"""

from django.conf import settings
from django.db import models

# Firebase's own provider ids, as they arrive in the token's
# ``firebase.sign_in_provider`` claim.
PROVIDER_PASSWORD = "password"
PROVIDER_GOOGLE = "google.com"

PROVIDER_LABELS = {
    PROVIDER_PASSWORD: "Email and password",
    PROVIDER_GOOGLE: "Google",
}


class FirebaseIdentity(models.Model):
    """A verified Firebase account, and the Django user it signs in as."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="firebase_identity",
    )
    # Firebase uids are 28 characters today; the field is wider so a
    # future format change does not need a migration.
    uid = models.CharField(max_length=128, unique=True)
    # The provider of the most recent sign-in. A customer may use both
    # Google and a password against one Firebase account, so this records
    # how they last signed in rather than how they registered.
    provider = models.CharField(max_length=64, blank=True)
    email = models.EmailField(blank=True)
    email_verified = models.BooleanField(default=False)
    display_name = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Firebase identity"
        verbose_name_plural = "Firebase identities"
        ordering = ["-created_at", "pk"]

    def __str__(self):
        return f"{self.email or self.uid} ({self.provider_display})"

    @property
    def provider_display(self):
        """The provider as a person would read it."""
        return PROVIDER_LABELS.get(self.provider, self.provider or "Unknown")

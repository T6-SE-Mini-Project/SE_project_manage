"""Turning a verified Firebase token into a Django user.

``accounts/firebase.py`` proves *who* a caller is; this module decides
*which Django user* that is, creating one on the customer's first sign-in.
Orders, carts, reviews and ``is_staff`` all hang off the Django user, so
every Firebase account needs exactly one, and it must be the same one on
every subsequent sign-in.
"""

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify

from .models import FirebaseIdentity

# Django's User.username is 150 characters. Leave room for the numeric
# suffix that de-duplicates a taken name.
USERNAME_MAX_LENGTH = 140


def profile_from_claims(claims):
    """The fields of an ID token this project stores, normalized.

    Only ``sub`` is guaranteed: a customer who signed up with Google and
    revoked the email scope, or an anonymous Firebase account, arrives
    with no email at all.
    """
    firebase_claim = claims.get("firebase")
    provider = ""
    if isinstance(firebase_claim, dict):
        provider = str(firebase_claim.get("sign_in_provider") or "")

    return {
        "uid": str(claims.get("sub", "")).strip(),
        "email": str(claims.get("email") or "").strip().lower(),
        "email_verified": bool(claims.get("email_verified")),
        "display_name": str(claims.get("name") or "").strip()[:150],
        "provider": provider[:64],
    }


def available_username(preferred):
    """Return ``preferred`` or the first free ``preferred-2``, ``-3``, ...

    Firebase has no concept of a username, but Django's User requires a
    unique one, so it is derived from the email address and only used for
    display and for the Django admin.
    """
    User = get_user_model()

    base = slugify(preferred)[:USERNAME_MAX_LENGTH].strip("-")
    if not base:
        base = "customer"

    if not User.objects.filter(username=base).exists():
        return base

    # Counting rows would collide as soon as one account is deleted, so
    # probe for the first free suffix instead.
    suffix = 2
    while User.objects.filter(username=f"{base}-{suffix}").exists():
        suffix += 1
    return f"{base}-{suffix}"


def _preferred_username(profile):
    """The username to try first for a brand-new account."""
    local_part = profile["email"].partition("@")[0]
    return local_part or profile["display_name"] or f"user-{profile['uid'][:12]}"


def _link_existing_user(profile):
    """Find the Django user this Firebase account should adopt, if any.

    This is what lets an account that predates Firebase — the
    administrator created with ``manage.py createsuperuser``, or a
    customer registered before this change — keep its orders, reviews and
    ``is_staff`` flag when its owner signs in through Firebase for the
    first time.

    The match is only made on an email address Firebase reports as
    **verified**. Firebase's email/password provider does not verify
    addresses by itself, so without that condition anyone could register
    ``admin@example.com`` in Firebase and be handed the existing
    administrator's Django account. A user who already has a Firebase
    identity is never adopted, so one customer cannot take over another's
    account either.
    """
    if not profile["email"] or not profile["email_verified"]:
        return None

    return (
        get_user_model()
        .objects.filter(
            email__iexact=profile["email"],
            firebase_identity__isnull=True,
        )
        .order_by("pk")
        .first()
    )


@transaction.atomic
def _create_identity(profile):
    """Create the Django user and identity row for a new Firebase uid."""
    user = _link_existing_user(profile)

    if user is None:
        user = get_user_model().objects.create_user(
            username=available_username(_preferred_username(profile)),
            email=profile["email"],
        )
        # Firebase holds the credentials. An unusable password means no
        # Django password check can ever succeed for this account, so the
        # Firebase token is the only way in.
        user.set_unusable_password()
        user.save(update_fields=["password"])
    elif profile["email"] and user.email.lower() != profile["email"]:
        user.email = profile["email"]
        user.save(update_fields=["email"])

    return FirebaseIdentity.objects.create(
        user=user,
        uid=profile["uid"],
        provider=profile["provider"],
        email=profile["email"],
        email_verified=profile["email_verified"],
        display_name=profile["display_name"],
    )


def identity_for_claims(claims):
    """Return the :class:`FirebaseIdentity` for a verified token.

    Creates the Django user on the customer's first sign-in and keeps the
    stored profile in step with Firebase on every later one. The uid is
    the only thing matched on, so changing an email address in Firebase
    moves the address rather than creating a second account.
    """
    profile = profile_from_claims(claims)
    if not profile["uid"]:
        raise ValueError("A Firebase token with no uid cannot identify a user.")

    identity = (
        FirebaseIdentity.objects.select_related("user")
        .filter(uid=profile["uid"])
        .first()
    )

    if identity is None:
        try:
            identity = _create_identity(profile)
        except IntegrityError:
            # Two requests from the same new customer can race here; the
            # unique constraint on uid decides, and the loser reads the
            # row the winner created.
            identity = FirebaseIdentity.objects.select_related("user").get(
                uid=profile["uid"]
            )
        return identity

    return refresh_identity(identity, profile)


def refresh_identity(identity, profile):
    """Write back any profile field Firebase now reports differently."""
    changed = [
        field
        for field in ("provider", "email", "email_verified", "display_name")
        if getattr(identity, field) != profile[field]
    ]

    if changed:
        for field in changed:
            setattr(identity, field, profile[field])
        identity.save(update_fields=changed)

    user = identity.user
    if profile["email"] and user.email.lower() != profile["email"]:
        user.email = profile["email"]
        user.save(update_fields=["email"])

    return identity


def record_sign_in(identity):
    """Stamp a successful sign-in, for the administrator's customer list.

    Called only from the sign-in endpoint, not from the middleware, so an
    ordinary API call does not write a row on every request.
    """
    now = timezone.now()

    identity.last_login_at = now
    identity.save(update_fields=["last_login_at"])

    # Keep Django's own last_login in step, so the admin site and the
    # administrator's customer screens show the same thing.
    identity.user.last_login = now
    identity.user.save(update_fields=["last_login"])

    return identity

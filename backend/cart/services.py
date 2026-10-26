from django.db import transaction

from .models import Cart


def get_cart(request):
    """Return the cart for this session, creating the session when needed."""
    if not request.session.session_key:
        request.session.create()

    user = request.user if request.user.is_authenticated else None
    cart, _ = Cart.objects.get_or_create(
        session_key=request.session.session_key,
    )

    if user is not None and cart.user_id != user.pk:
        cart.user = user
        cart.save(update_fields=["user", "updated_at"])

    return cart


@transaction.atomic
def reassign_cart_session(previous_session_key, new_session_key, user=None):
    """Move a cart to a new session key after the key is cycled.

    Logging in and registering call ``django.contrib.auth.login()``, which
    cycles the session key. Carts are keyed by that value, so without this
    the customer's guest cart would be silently dropped at login.

    Returns the surviving cart, or ``None`` when there was nothing to move.
    """
    if not previous_session_key or previous_session_key == new_session_key:
        return None

    previous_cart = Cart.objects.filter(
        session_key=previous_session_key
    ).first()

    if previous_cart is None:
        return None

    owner = user if user is not None and user.is_authenticated else None
    existing_cart = Cart.objects.filter(session_key=new_session_key).first()

    if existing_cart is None:
        previous_cart.session_key = new_session_key
        previous_cart.user = owner
        previous_cart.save(
            update_fields=["session_key", "user", "updated_at"]
        )
        return previous_cart

    # The new session already has a cart: merge the guest lines into it,
    # adding quantities for books that are in both.
    for item in previous_cart.items.all():
        existing_item = existing_cart.items.filter(book=item.book).first()

        if existing_item is None:
            item.cart = existing_cart
            item.save(update_fields=["cart", "updated_at"])
        else:
            existing_item.quantity += item.quantity
            existing_item.save(update_fields=["quantity", "updated_at"])

    previous_cart.delete()

    if owner is not None and existing_cart.user_id != owner.pk:
        existing_cart.user = owner
        existing_cart.save(update_fields=["user", "updated_at"])

    return existing_cart

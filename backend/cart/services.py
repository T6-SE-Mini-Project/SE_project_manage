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

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from cart.services import get_cart

from .models import Order
from .serializers import serialize_order, serialize_order_summary
from .services import check_cart_availability, place_order_from_cart


def _current_user(request):
    user = request.user
    return user if user.is_authenticated else None


def _orders_for_request(request):
    """Orders placed from this session (guest or authenticated customer)."""
    if not request.session.session_key:
        return Order.objects.none()

    return Order.objects.filter(session_key=request.session.session_key)


def _get_scoped_order(request, pk):
    """Return the order for this session or ``None`` when not found."""
    return (
        _orders_for_request(request)
        .filter(pk=pk)
        .prefetch_related("items")
        .first()
    )


@require_http_methods(["GET", "POST"])
def order_collection(request):
    """GET lists this session's orders; POST places a new order."""
    if request.method == "GET":
        orders = _orders_for_request(request).prefetch_related("items")
        return JsonResponse(
            {
                "count": orders.count(),
                "orders": [
                    serialize_order_summary(order) for order in orders
                ],
            }
        )

    cart = get_cart(request)
    order, problems = place_order_from_cart(
        cart,
        user=_current_user(request),
    )

    if problems:
        return JsonResponse(
            {
                "error": (
                    "Your order cannot be placed because some books are "
                    "not available in the requested quantity."
                ),
                "availability": problems,
            },
            status=409,
        )

    return JsonResponse(
        {"order": serialize_order(order)},
        status=201,
    )


@require_http_methods(["GET"])
def order_availability(request):
    """Report availability problems for the current cart (pre-checkout)."""
    cart = get_cart(request)
    problems = check_cart_availability(cart)

    return JsonResponse(
        {
            "available": not problems,
            "problems": problems,
        }
    )


@require_http_methods(["GET"])
def order_detail(request, pk):
    order = _get_scoped_order(request, pk)

    if order is None:
        return JsonResponse({"error": "Order not found."}, status=404)

    return JsonResponse({"order": serialize_order(order)})

from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST

from cart.services import get_cart
from config.http import json_error, read_json

from .models import Order
from .serializers import serialize_order
from .services import (
    cancel_order,
    check_cart_availability,
    place_order_from_cart,
)


def _current_user(request):
    user = request.user
    return user if user.is_authenticated else None


def _orders_for_request(request):
    """Orders this caller is allowed to see (issue #10).

    An authenticated customer sees every order on their account, plus any
    order they placed as a guest earlier in the same browser session, so
    logging in never hides an order. A guest sees only this session's
    orders.
    """
    session_key = request.session.session_key
    user = _current_user(request)

    if user is None:
        if not session_key:
            return Order.objects.none()
        return Order.objects.filter(session_key=session_key)

    scope = Q(user=user)
    if session_key:
        scope |= Q(session_key=session_key, user__isnull=True)

    return Order.objects.filter(scope)


def _get_scoped_order(request, pk):
    """Return the order for this caller or ``None`` when not found."""
    return (
        _orders_for_request(request)
        .filter(pk=pk)
        .prefetch_related("items")
        .first()
    )


@require_http_methods(["GET", "POST"])
def order_collection(request):
    """GET lists this customer's order history; POST places a new order."""
    if request.method == "GET":
        orders = list(
            _orders_for_request(request).prefetch_related("items")
        )
        return JsonResponse(
            {
                "count": len(orders),
                "orders": [serialize_order(order) for order in orders],
            }
        )

    cart = get_cart(request)
    order, problems = place_order_from_cart(
        cart,
        user=_current_user(request),
    )

    if problems:
        return json_error(
            "Your order cannot be placed because some books are not "
            "available in the requested quantity.",
            409,
            availability=problems,
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
        return json_error("Order not found.", 404)

    return JsonResponse({"order": serialize_order(order)})


@require_POST
def order_cancel(request, pk):
    """Cancel one of this customer's orders when it is eligible (issue #10)."""
    order = _get_scoped_order(request, pk)

    if order is None:
        return json_error("Order not found.", 404)

    data, error_response = read_json(request)
    if error_response is not None:
        return error_response

    cancelled, error = cancel_order(
        order,
        reason=str(data.get("reason", "")),
    )

    if error is not None:
        # The order exists and belongs to the caller, but its current
        # status does not satisfy the cancellation conditions.
        return json_error(error, 409, order=serialize_order(order))

    cancelled = (
        Order.objects.prefetch_related("items").get(pk=cancelled.pk)
    )

    return JsonResponse({"order": serialize_order(cancelled)})

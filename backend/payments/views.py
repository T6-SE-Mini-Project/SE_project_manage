from django.http import JsonResponse
from django.views.decorators.http import require_POST

from config.cache import BOOKS, CART, ORDERS, invalidate
from config.http import json_error, read_json
from orders.models import Order
from orders.serializers import serialize_order

from .serializers import serialize_payment
from .services import process_order_payment


@require_POST
def payment_create(request):
    """Process payment for an order and confirm it on success."""
    data, error_response = read_json(request)
    if error_response is not None:
        return error_response

    order_id = data.get("order_id")
    if isinstance(order_id, str) and order_id.isdigit():
        order_id = int(order_id)

    if not isinstance(order_id, int):
        return json_error("order_id is required.", 400)

    session_key = request.session.session_key or ""
    order = (
        Order.objects.filter(pk=order_id, session_key=session_key)
        .prefetch_related("items")
        .first()
    )

    if order is None:
        return json_error("Order not found.", 404)

    user = request.user if request.user.is_authenticated else None
    outcome = process_order_payment(order, data, user=user)

    if not outcome.succeeded:
        body = {"error": outcome.error}

        if outcome.payment is not None:
            body["payment"] = serialize_payment(outcome.payment)
        if outcome.availability:
            body["availability"] = outcome.availability

        return JsonResponse(body, status=outcome.status)

    order.refresh_from_db()

    # A successful payment confirms the order and reserves its stock, so
    # the catalogue, the order history and the cart all changed.
    invalidate(ORDERS, BOOKS, CART)

    return JsonResponse(
        {
            "order": serialize_order(order),
            "payment": serialize_payment(outcome.payment),
        },
        status=200,
    )

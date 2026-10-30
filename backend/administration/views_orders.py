"""Administrator order management (issue #12, OBS-F-018, TC-OBS-017).

Administrators see every order (customers only ever see their own) and
can move an order through fulfilment or cancel it. Cancellation reuses
``orders.services.cancel_order``, so an administrator cancellation
releases reserved stock exactly like a customer cancellation.
"""

from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from config.cache import BOOKS, ORDERS, TTL_ADMIN, cached_json, invalidate
from config.http import json_error, read_json, staff_required_api
from orders.models import Order
from orders.serializers import serialize_order, serialize_order_summary
from orders.services import (
    ALLOWED_STATUS_TRANSITIONS,
    cancel_order,
    update_order_status,
)

#: Maximum number of orders returned in one page of the order list.
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def _parse_page_size(raw):
    if raw is None or str(raw).strip() == "":
        return DEFAULT_PAGE_SIZE, None

    try:
        limit = int(raw)
    except (TypeError, ValueError):
        return None, "limit must be a whole number."

    if limit < 1:
        return None, "limit must be at least 1."

    return min(limit, MAX_PAGE_SIZE), None


@require_GET
@staff_required_api
@cached_json(TTL_ADMIN, namespaces=[ORDERS])
def order_collection(request):
    """List all orders, newest first, with status and customer filters."""
    orders = Order.objects.select_related("user").prefetch_related("items")

    status = request.GET.get("status", "").strip().upper()
    search = request.GET.get("q", "").strip()

    if status:
        valid_statuses = {choice for choice, _ in Order.STATUS_CHOICES}
        if status not in valid_statuses:
            return json_error(
                f"{status!r} is not a valid order status.",
                400,
            )
        orders = orders.filter(status=status)

    if search:
        scope = Q(user__username__icontains=search) | Q(
            user__email__icontains=search
        )
        if search.isdigit():
            scope |= Q(pk=int(search))
        orders = orders.filter(scope)

    limit, error = _parse_page_size(request.GET.get("limit"))
    if error is not None:
        return json_error(error, 400)

    offset, error = (0, None)
    raw_offset = request.GET.get("offset")
    if raw_offset is not None and str(raw_offset).strip() != "":
        try:
            offset = max(int(raw_offset), 0)
        except (TypeError, ValueError):
            return json_error("offset must be a whole number.", 400)

    total = orders.count()
    page = list(orders[offset : offset + limit])

    return JsonResponse(
        {
            "count": total,
            "limit": limit,
            "offset": offset,
            "orders": [serialize_order_summary(order) for order in page],
            # Lets the admin UI render only the transitions the server
            # will accept for each status.
            "allowed_transitions": {
                status: sorted(targets)
                for status, targets in ALLOWED_STATUS_TRANSITIONS.items()
            },
        }
    )


@require_GET
@staff_required_api
@cached_json(TTL_ADMIN, namespaces=[ORDERS])
def order_detail(request, pk):
    order = (
        Order.objects.select_related("user")
        .prefetch_related("items", "payments")
        .filter(pk=pk)
        .first()
    )

    if order is None:
        return json_error("Order not found.", 404)

    data = serialize_order(order)
    data["customer"] = (
        {
            "id": order.user_id,
            "username": order.user.username,
            "email": order.user.email,
        }
        if order.user_id
        else None
    )
    data["session_key"] = order.session_key
    data["payments"] = [
        {
            "id": payment.id,
            "amount": f"{payment.amount:.2f}",
            "status": payment.status,
            "method": payment.method,
            "reference": payment.reference,
            "failure_reason": payment.failure_reason,
            "card_last4": payment.card_last4,
            "created_at": payment.created_at.isoformat(),
        }
        for payment in order.payments.all()
    ]

    return JsonResponse({"order": data})


@require_POST
@staff_required_api
def order_status(request, pk):
    """Move an order to the next fulfilment status."""
    order = Order.objects.filter(pk=pk).first()

    if order is None:
        return json_error("Order not found.", 404)

    data, error_response = read_json(request)
    if error_response is not None:
        return error_response

    new_status = str(data.get("status", "")).strip().upper()

    if not new_status:
        return json_error("status is required.", 400)

    updated, error = update_order_status(order, new_status)

    if error is not None:
        return json_error(error, 409)

    updated = (
        Order.objects.select_related("user")
        .prefetch_related("items")
        .get(pk=updated.pk)
    )

    invalidate(ORDERS)

    return JsonResponse({"order": serialize_order_summary(updated)})


@require_POST
@staff_required_api
def order_cancel(request, pk):
    """Cancel an order on a customer's behalf, releasing reserved stock."""
    order = Order.objects.filter(pk=pk).first()

    if order is None:
        return json_error("Order not found.", 404)

    data, error_response = read_json(request)
    if error_response is not None:
        return error_response

    cancelled, error = cancel_order(
        order,
        reason=str(data.get("reason", "")),
        by_staff=True,
    )

    if error is not None:
        return json_error(error, 409)

    cancelled = (
        Order.objects.select_related("user")
        .prefetch_related("items")
        .get(pk=cancelled.pk)
    )

    # Cancelling releases the order's reserved stock.
    invalidate(ORDERS, BOOKS)

    return JsonResponse({"order": serialize_order_summary(cancelled)})

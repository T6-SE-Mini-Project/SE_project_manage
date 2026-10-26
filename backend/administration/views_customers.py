"""Administrator customer management (issue #24).

Administrators can review customer accounts with their order history and
deactivate or reactivate an account. Accounts are never deleted: orders
reference the customer, and deactivating preserves that history while
immediately preventing new logins (Django's ``AuthenticationForm``
rejects inactive users).
"""

from django.contrib.auth.models import User
from django.db.models import Count, Max, Q, Sum
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from config.http import json_error, read_json, staff_required_api
from orders.models import Order
from orders.serializers import serialize_order_summary

from .serializers import customer_stats, serialize_customer

#: Revenue-bearing order filter reused by the annotations below.
_PAID_ORDERS = Q(orders__status__in=Order.REVENUE_STATUSES)


def _customer_queryset():
    """Customers annotated with their order aggregates."""
    return User.objects.annotate(
        order_count=Count("orders", distinct=True),
        cancelled_order_count=Count(
            "orders",
            filter=Q(orders__status=Order.STATUS_CANCELLED),
            distinct=True,
        ),
        total_spent=Sum("orders__total_amount", filter=_PAID_ORDERS),
        last_order_at=Max("orders__created_at"),
    )


@require_GET
@staff_required_api
def customer_collection(request):
    """List customer accounts with their order totals."""
    customers = _customer_queryset()

    search = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip().lower()

    if search:
        customers = customers.filter(
            Q(username__icontains=search) | Q(email__icontains=search)
        )

    if status == "active":
        customers = customers.filter(is_active=True)
    elif status == "inactive":
        customers = customers.filter(is_active=False)
    elif status not in {"", "all"}:
        return json_error(
            "status must be one of: active, inactive, all.",
            400,
        )

    customers = list(customers.order_by("username"))

    return JsonResponse(
        {
            "count": len(customers),
            "customers": [
                serialize_customer(customer, customer_stats(customer))
                for customer in customers
            ],
        }
    )


@require_GET
@staff_required_api
def customer_detail(request, pk):
    """One customer account with their recent orders."""
    customer = _customer_queryset().filter(pk=pk).first()

    if customer is None:
        return json_error("Customer not found.", 404)

    orders = (
        Order.objects.filter(user=customer)
        .select_related("user")
        .prefetch_related("items")
    )

    data = serialize_customer(customer, customer_stats(customer))
    data["orders"] = [serialize_order_summary(order) for order in orders]

    return JsonResponse({"customer": data})


@require_POST
@staff_required_api
def customer_status(request, pk):
    """Activate or deactivate a customer account."""
    customer = User.objects.filter(pk=pk).first()

    if customer is None:
        return json_error("Customer not found.", 404)

    data, error_response = read_json(request)
    if error_response is not None:
        return error_response

    is_active = data.get("is_active")

    if not isinstance(is_active, bool):
        return json_error("is_active must be true or false.", 400)

    if customer.pk == request.user.pk:
        # Deactivating your own account would lock you out of the admin
        # screens mid-session.
        return json_error(
            "You cannot change the status of your own account.",
            400,
        )

    if customer.is_staff and not is_active:
        return json_error(
            "Administrator accounts cannot be deactivated from this "
            "screen.",
            403,
        )

    customer.is_active = is_active
    customer.save(update_fields=["is_active"])

    refreshed = _customer_queryset().get(pk=customer.pk)

    return JsonResponse(
        {"customer": serialize_customer(refreshed, customer_stats(refreshed))}
    )

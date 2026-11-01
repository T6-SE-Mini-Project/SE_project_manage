import json

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .forms import BillingAddressForm
from .models import BillingAddress, Order
from .serializers import serialize_billing_address, serialize_order_detail
from .services import CheckoutError, place_order


def _read_json(request):
    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, JsonResponse(
            {"error": "Invalid JSON body."},
            status=400,
        )

    if not isinstance(data, dict):
        return None, JsonResponse(
            {"error": "JSON body must be an object."},
            status=400,
        )

    return data, None


def _form_errors(form):
    return {
        field: [entry["message"] for entry in entries]
        for field, entries in form.errors.get_json_data().items()
    }


@require_GET
def billing_address_list(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Sign in to view saved billing addresses."},
            status=401,
        )

    addresses = BillingAddress.objects.filter(user=request.user)

    return JsonResponse(
        {
            "addresses": [
                serialize_billing_address(address)
                for address in addresses
            ]
        }
    )


@require_POST
def checkout(request):
    data, error_response = _read_json(request)
    if error_response is not None:
        return error_response

    billing_data = data.get("billing_address")
    if not isinstance(billing_data, dict):
        return JsonResponse(
            {
                "error": "billing_address must be an object.",
                "errors": {
                    "billing_address": [
                        "Billing address details are required."
                    ]
                },
            },
            status=400,
        )

    save_address = data.get("save_address", False)
    if not isinstance(save_address, bool):
        return JsonResponse(
            {"error": "save_address must be true or false."},
            status=400,
        )

    form = BillingAddressForm(data=billing_data)
    if not form.is_valid():
        return JsonResponse(
            {
                "error": "Please correct the highlighted fields.",
                "errors": _form_errors(form),
            },
            status=400,
        )

    try:
        order, address_saved = place_order(
            request,
            form,
            save_address=save_address,
        )
    except CheckoutError as exc:
        return JsonResponse(
            {"error": exc.message, "errors": exc.errors or {}},
            status=exc.status,
        )

    order = (
        Order.objects.select_related("billing_address")
        .prefetch_related("items__book")
        .get(pk=order.pk)
    )

    return JsonResponse(
        {
            "order": serialize_order_detail(order),
            "address_saved": address_saved,
        },
        status=201,
    )


def _can_access_order(request, order):
    if order.user_id is not None:
        return (
            request.user.is_authenticated
            and request.user.pk == order.user_id
        )

    return bool(
        request.session.session_key
        and request.session.session_key == order.session_key
    )


@require_GET
def order_detail(request, pk):
    order = (
        Order.objects.select_related("billing_address")
        .prefetch_related("items__book")
        .filter(pk=pk)
        .first()
    )

    if order is None or not _can_access_order(request, order):
        return JsonResponse({"error": "Order not found."}, status=404)

    return JsonResponse({"order": serialize_order_detail(order)})

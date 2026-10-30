"""Sales report endpoint (issue #24)."""

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from config.cache import ORDERS, TTL_REPORTS, cached_json
from config.http import json_error, staff_required_api

from .reports import ReportPeriodError, build_sales_report, parse_period
from .serializers import serialize_sales_report


# The most expensive read in the project: aggregates over every paid
# order and its lines. Worth the longest TTL here.
@require_GET
@staff_required_api
@cached_json(TTL_REPORTS, namespaces=[ORDERS])
def sales_report(request):
    """Generate a sales report for an optional ``start``/``end`` period."""
    try:
        start, end = parse_period(
            request.GET.get("start"),
            request.GET.get("end"),
        )
    except ReportPeriodError as exc:
        return json_error(str(exc), 400)

    report = build_sales_report(start=start, end=end)

    return JsonResponse({"report": serialize_sales_report(report)})

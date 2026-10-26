"""Sales report generation (issue #24).

The report is derived entirely from stored order data, so it can be
reproduced for any period. Only orders in ``Order.REVENUE_STATUSES``
count towards revenue: a pending order has not been paid for and a
cancelled order has been refunded or never charged, so neither is
revenue.
"""

from datetime import datetime, time
from decimal import Decimal

from django.db.models import Count, F, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from orders.models import Order, OrderItem

#: How many best-selling titles the report lists.
TOP_BOOK_LIMIT = 10


class ReportPeriodError(ValueError):
    """Raised when the requested report period cannot be parsed."""


def parse_period(raw_start, raw_end):
    """Parse ``start``/``end`` query values into dates.

    Both are optional: an open-ended period reports over all stored
    orders. Returns ``(start_date, end_date)``.
    """

    def parse_one(raw, name):
        if raw is None or str(raw).strip() == "":
            return None
        try:
            return datetime.strptime(str(raw).strip(), "%Y-%m-%d").date()
        except ValueError as exc:
            raise ReportPeriodError(
                f"{name} must be a date in YYYY-MM-DD format."
            ) from exc

    start = parse_one(raw_start, "start")
    end = parse_one(raw_end, "end")

    if start and end and start > end:
        raise ReportPeriodError("start cannot be later than end.")

    return start, end


def _restrict_to_period(queryset, start, end, field="created_at"):
    """Filter a queryset to the requested period, inclusive of both days."""
    current_timezone = timezone.get_current_timezone()

    if start is not None:
        queryset = queryset.filter(
            **{
                f"{field}__gte": timezone.make_aware(
                    datetime.combine(start, time.min), current_timezone
                )
            }
        )

    if end is not None:
        queryset = queryset.filter(
            **{
                f"{field}__lte": timezone.make_aware(
                    datetime.combine(end, time.max), current_timezone
                )
            }
        )

    return queryset


def build_sales_report(start=None, end=None):
    """Return the sales figures for the given period.

    The result is a plain dict; ``administration.serializers`` turns it
    into the API payload.
    """
    orders = _restrict_to_period(Order.objects.all(), start, end)
    revenue_orders = orders.filter(status__in=Order.REVENUE_STATUSES)

    totals = revenue_orders.aggregate(
        revenue=Sum("total_amount"),
        order_count=Count("pk"),
    )
    revenue_total = totals["revenue"] or Decimal("0.00")
    revenue_order_count = totals["order_count"] or 0

    average_order_value = (
        (revenue_total / revenue_order_count).quantize(Decimal("0.01"))
        if revenue_order_count
        else Decimal("0.00")
    )

    # Every order status is reported, including the ones excluded from
    # revenue, so the administrator can see pending and cancelled volume.
    status_counts = {
        status: 0 for status, _ in Order.STATUS_CHOICES
    }
    for row in orders.values("status").annotate(total=Count("pk")):
        status_counts[row["status"]] = row["total"]

    revenue_items = OrderItem.objects.filter(order__in=revenue_orders)

    items_sold = revenue_items.aggregate(total=Sum("quantity"))["total"] or 0

    top_books = [
        {
            "book_id": row["book_id"],
            "title": row["book_title"],
            "quantity_sold": row["quantity_sold"],
            "revenue": f"{row['revenue'] or Decimal('0.00'):.2f}",
        }
        for row in revenue_items.values("book_id", "book_title")
        .annotate(
            quantity_sold=Sum("quantity"),
            revenue=Sum(F("unit_price") * F("quantity")),
        )
        .order_by("-quantity_sold", "book_title")[:TOP_BOOK_LIMIT]
    ]

    daily = [
        {
            "date": row["day"].isoformat(),
            "order_count": row["order_count"],
            "revenue": f"{row['revenue'] or Decimal('0.00'):.2f}",
        }
        for row in revenue_orders.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            order_count=Count("pk"),
            revenue=Sum("total_amount"),
        )
        .order_by("day")
    ]

    return {
        "start": start,
        "end": end,
        "revenue_total": revenue_total,
        "revenue_order_count": revenue_order_count,
        "average_order_value": average_order_value,
        "items_sold": items_sold,
        "orders_by_status": status_counts,
        "top_books": top_books,
        "daily": daily,
        "generated_at": timezone.now(),
    }

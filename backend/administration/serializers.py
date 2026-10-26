"""Serializers for the administrator API (issues #12 and #24)."""

from decimal import Decimal

from orders.models import Order


def serialize_customer(user, stats=None):
    """A customer account as shown in the administrator customer list.

    ``stats`` carries the aggregates annotated on the queryset so the
    list view does not run a query per customer.
    """
    data = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active,
        "is_staff": user.is_staff,
        "date_joined": user.date_joined.isoformat(),
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }

    if stats is not None:
        data.update(stats)

    return data


def customer_stats(user):
    """Order aggregates annotated onto a customer row by the list view."""
    return {
        "order_count": getattr(user, "order_count", 0) or 0,
        "cancelled_order_count": getattr(user, "cancelled_order_count", 0) or 0,
        "total_spent": f"{getattr(user, 'total_spent', None) or Decimal('0.00'):.2f}",
        "last_order_at": (
            user.last_order_at.isoformat()
            if getattr(user, "last_order_at", None)
            else None
        ),
    }


def serialize_sales_report(report):
    """The sales report payload (issue #24)."""
    return {
        "period": {
            "start": report["start"].isoformat() if report["start"] else None,
            "end": report["end"].isoformat() if report["end"] else None,
        },
        "revenue": {
            "total": f"{report['revenue_total']:.2f}",
            "order_count": report["revenue_order_count"],
            "average_order_value": f"{report['average_order_value']:.2f}",
            "items_sold": report["items_sold"],
            # Which statuses count towards revenue, so the figures in the
            # report can be reproduced.
            "counted_statuses": sorted(Order.REVENUE_STATUSES),
        },
        "orders_by_status": report["orders_by_status"],
        "top_books": report["top_books"],
        "daily": report["daily"],
        "generated_at": report["generated_at"].isoformat(),
    }

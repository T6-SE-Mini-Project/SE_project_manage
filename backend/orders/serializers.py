def _cancellation_fields(order):
    """Cancellation state shared by the order representations (issue #10)."""
    return {
        "is_cancelled": order.is_cancelled,
        "is_cancellable": order.is_cancellable,
        "cancelled_at": (
            order.cancelled_at.isoformat() if order.cancelled_at else None
        ),
        "cancellation_reason": order.cancellation_reason,
        "refund_due": order.refund_due,
    }


def serialize_order(order):
    """Full order representation used for details, history and confirmations."""
    return {
        "id": order.id,
        "status": order.status,
        "status_display": order.status_display,
        "is_confirmed": order.is_confirmed,
        "is_paid": order.is_paid,
        "total_amount": f"{order.total_amount:.2f}",
        "item_count": sum(item.quantity for item in order.items.all()),
        "items": [
            {
                "id": item.id,
                "book_id": item.book_id,
                "title": item.book_title,
                "unit_price": f"{item.unit_price:.2f}",
                "quantity": item.quantity,
                "line_total": f"{item.line_total:.2f}",
            }
            for item in order.items.all()
        ],
        "created_at": order.created_at.isoformat(),
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        **_cancellation_fields(order),
    }


def serialize_order_summary(order):
    """Compact order representation used in the administrator order list."""
    return {
        "id": order.id,
        "status": order.status,
        "status_display": order.status_display,
        "is_confirmed": order.is_confirmed,
        "is_paid": order.is_paid,
        "total_amount": f"{order.total_amount:.2f}",
        "item_count": sum(item.quantity for item in order.items.all()),
        "created_at": order.created_at.isoformat(),
        "customer": (
            {
                "id": order.user_id,
                "username": order.user.username,
                "email": order.user.email,
            }
            if order.user_id
            else None
        ),
        **_cancellation_fields(order),
    }

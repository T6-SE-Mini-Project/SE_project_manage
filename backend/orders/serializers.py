def serialize_order(order):
    """Full order representation used for details and confirmations."""
    return {
        "id": order.id,
        "status": order.status,
        "is_confirmed": order.is_confirmed,
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
    }


def serialize_order_summary(order):
    """Compact order representation used in order lists."""
    return {
        "id": order.id,
        "status": order.status,
        "is_confirmed": order.is_confirmed,
        "total_amount": f"{order.total_amount:.2f}",
        "item_count": sum(item.quantity for item in order.items.all()),
        "created_at": order.created_at.isoformat(),
    }

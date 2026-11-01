from books.serializers import serialize_book_summary


def serialize_billing_address(address):
    return {
        "id": address.id,
        "full_name": address.full_name,
        "phone_number": address.phone_number,
        "email": address.email,
        "address_line1": address.address_line1,
        "address_line2": address.address_line2,
        "city": address.city,
        "state": address.state,
        "postal_code": address.postal_code,
        "country": address.country,
        "created_at": address.created_at.isoformat(),
        "updated_at": address.updated_at.isoformat(),
    }


def serialize_order_summary(order):
    return {
        "id": order.id,
        "reference": str(order.reference),
        "short_reference": order.short_reference,
        "status": order.status,
        "status_label": order.get_status_display(),
        "total": f"{order.total:.2f}",
        "item_count": sum(item.quantity for item in order.items.all()),
        "created_at": order.created_at.isoformat(),
    }


def serialize_order_detail(order):
    items = list(order.items.select_related("book").order_by("pk"))

    return {
        **serialize_order_summary(order),
        "billing_address": serialize_billing_address(order.billing_address),
        "items": [
            {
                "id": item.id,
                "book": serialize_book_summary(item.book),
                "title": item.title,
                "unit_price": f"{item.unit_price:.2f}",
                "quantity": item.quantity,
                "subtotal": f"{item.subtotal:.2f}",
            }
            for item in items
        ],
    }

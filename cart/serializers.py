from decimal import Decimal

from books.serializers import serialize_book_summary


def serialize_cart(cart):
    items = list(
        cart.items.select_related("book").order_by("added_at", "pk")
    )
    total = sum(
        (item.subtotal for item in items),
        Decimal("0.00"),
    )

    return {
        "items": [
            {
                "id": item.id,
                "book": serialize_book_summary(item.book),
                "quantity": item.quantity,
                "subtotal": f"{item.subtotal:.2f}",
            }
            for item in items
        ],
        "total": f"{total:.2f}",
        "item_count": sum(item.quantity for item in items),
    }

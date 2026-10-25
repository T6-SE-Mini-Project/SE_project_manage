def _serialize_common(book):
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "isbn": book.isbn,
        "category": book.category,
        "price": str(book.price),
        "stock_quantity": book.stock_quantity,
        "in_stock": book.in_stock,
        "cover_image_url": book.cover_image_url,
    }


def serialize_book_summary(book):
    """Book fields needed to render a catalogue card."""
    return _serialize_common(book)


def serialize_book_detail(book):
    """Book fields needed to render the individual book details page."""
    data = _serialize_common(book)
    data.update(
        {
            "description": book.description,
            "publisher": book.publisher,
            "publication_date": (
                book.publication_date.isoformat()
                if book.publication_date
                else None
            ),
            "created_at": book.created_at.isoformat(),
            "updated_at": book.updated_at.isoformat(),
        }
    )
    return data

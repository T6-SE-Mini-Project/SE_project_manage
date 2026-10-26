import { Link } from "react-router-dom";

import { formatPrice } from "../format";
import type { BookSummary } from "../types";
import BookCover from "./BookCover";

interface BookCardProps {
  book: BookSummary;
}

export default function BookCard({ book }: BookCardProps) {
  return (
    <article className="book-card">
      <Link
        to={`/books/${book.id}`}
        className="book-cover-link"
        aria-label={`View details for ${book.title}`}
      >
        <BookCover book={book} />
      </Link>

      <div className="book-card-body">
        <p className="book-category">{book.category}</p>
        <h2 className="book-title">
          <Link to={`/books/${book.id}`}>{book.title}</Link>
        </h2>
        <p className="book-author">{book.author}</p>
        <div className="book-card-footer">
          <span className="book-price">{formatPrice(book.price)}</span>
          <span
            className={
              book.in_stock ? "stock-badge in-stock" : "stock-badge out-of-stock"
            }
          >
            {book.in_stock ? "In stock" : "Out of stock"}
          </span>
        </div>
      </div>
    </article>
  );
}

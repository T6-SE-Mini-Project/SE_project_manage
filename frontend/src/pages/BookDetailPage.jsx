import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { addToCart, getBook } from "../api";
import AddToCartButton from "../components/AddToCartButton";
import BookCover from "../components/BookCover";
import { formatDate, formatPrice } from "../format";

export default function BookDetailPage() {
  const { bookId } = useParams();

  const [book, setBook] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notFound, setNotFound] = useState(false);
  const [adding, setAdding] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [added, setAdded] = useState(false);

  useEffect(() => {
    let active = true;

    setLoading(true);
    setError("");
    setNotFound(false);
    setBook(null);
    setFeedback(null);
    setAdded(false);

    getBook(bookId)
      .then((data) => {
        if (active) {
          setBook(data.book);
        }
      })
      .catch((requestError) => {
        if (!active) {
          return;
        }
        if (requestError.status === 404) {
          setNotFound(true);
        } else {
          setError(requestError.message);
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [bookId]);

  async function handleAdd() {
    if (!book) {
      return;
    }

    setAdding(true);
    setFeedback(null);

    try {
      await addToCart(book.id);
      setAdded(true);
      setFeedback({ type: "success", text: "Added to cart." });
    } catch (requestError) {
      setFeedback({ type: "error", text: requestError.message });
    } finally {
      setAdding(false);
    }
  }

  if (loading) {
    return <div className="status-panel">Loading book details...</div>;
  }

  if (notFound) {
    return (
      <div className="status-panel">
        <h1>Book not found</h1>
        <p>The requested book is not available in the catalogue.</p>
        <Link className="text-link" to="/books">
          Back to the catalogue
        </Link>
      </div>
    );
  }

  if (error || !book) {
    return (
      <div className="status-panel">
        <h1>Could not load this book</h1>
        <p>{error || "An unexpected error occurred."}</p>
        <Link className="text-link" to="/books">
          Back to the catalogue
        </Link>
      </div>
    );
  }

  return (
    <article className="book-detail">
      <Link className="back-link" to="/books">
        ← Back to catalogue
      </Link>

      <div className="book-detail-grid">
        <div>
          <BookCover book={book} className="book-cover detail-cover" />
        </div>

        <div className="book-detail-info">
          <p className="book-category">{book.category}</p>
          <h1>{book.title}</h1>
          <p className="book-author">by {book.author}</p>
          <p className="book-price detail-price">{formatPrice(book.price)}</p>

          <p
            className={
              book.in_stock ? "availability in-stock" : "availability out-of-stock"
            }
          >
            {book.in_stock
              ? `${book.stock_quantity} in stock`
              : "Currently out of stock"}
          </p>

          <div className="detail-actions">
            <AddToCartButton
              onAdd={handleAdd}
              busy={adding}
              disabled={!book.in_stock}
            />
            {added ? (
              <Link className="text-link" to="/cart">
                View cart
              </Link>
            ) : null}
          </div>

          {feedback ? (
            <p className={`feedback ${feedback.type}`} role="status">
              {feedback.text}
            </p>
          ) : null}

          <dl className="book-metadata">
            <div>
              <dt>ISBN</dt>
              <dd>{book.isbn}</dd>
            </div>
            <div>
              <dt>Publisher</dt>
              <dd>{book.publisher || "Not specified"}</dd>
            </div>
            <div>
              <dt>Published</dt>
              <dd>{formatDate(book.publication_date)}</dd>
            </div>
            <div>
              <dt>Category</dt>
              <dd>{book.category}</dd>
            </div>
          </dl>
        </div>
      </div>

      <section className="book-description">
        <h2>About this book</h2>
        <p>{book.description || "No description is available for this title yet."}</p>
      </section>
    </article>
  );
}

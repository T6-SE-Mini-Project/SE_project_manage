import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import BookCover from "../components/BookCover";
import {
  useCart,
  useRemoveCartItem,
  useUpdateCartItem,
} from "../hooks/useBookStore";
import { formatPrice } from "../format";

export default function CartPage() {
  const navigate = useNavigate();

  const cartQuery = useCart();
  const updateMutation = useUpdateCartItem();
  const removeMutation = useRemoveCartItem();

  const [pendingItemId, setPendingItemId] = useState<number | null>(null);
  const [error, setError] = useState("");

  const cart = cartQuery.data?.cart;

  async function runItemAction(itemId: number, action: () => Promise<unknown>) {
    setPendingItemId(itemId);
    setError("");

    try {
      await action();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not update the cart.",
      );
    } finally {
      setPendingItemId(null);
    }
  }

  function changeQuantity(item: { id: number; quantity: number; book: { stock_quantity: number } }, quantity: number) {
    if (quantity < 1 || quantity > item.book.stock_quantity) {
      return;
    }
    void runItemAction(item.id, () =>
      updateMutation.mutateAsync({ itemId: item.id, quantity }),
    );
  }

  function removeItem(itemId: number) {
    void runItemAction(itemId, () => removeMutation.mutateAsync(itemId));
  }

  if (cartQuery.isPending) {
    return <div className="status-panel">Loading your cart...</div>;
  }

  if (cartQuery.isError) {
    return (
      <div className="status-panel">
        <h1>Could not load your cart</h1>
        <p>{cartQuery.error.message}</p>
        <Link className="text-link" to="/books">
          Back to the catalogue
        </Link>
      </div>
    );
  }

  if (!cart) {
    return null;
  }

  return (
    <section className="cart-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Shopping cart</p>
          <h1>Your cart</h1>
          <p className="page-intro">
            Update quantities or remove a title. The total is recalculated from
            the current cart contents.
          </p>
        </div>
      </header>

      {error ? (
        <div className="alert error" role="alert">
          {error}
        </div>
      ) : null}

      {cart.items.length === 0 ? (
        <div className="empty-state">
          <h2>Your cart is empty</h2>
          <p>Browse the catalogue and add a book to get started.</p>
          <Link className="button primary" to="/books">
            Browse books
          </Link>
        </div>
      ) : (
        <div className="cart-layout">
          <div className="cart-items">
            {cart.items.map((item) => {
              const pending = pendingItemId === item.id;

              return (
                <article className="cart-row" key={item.id}>
                  <Link to={`/books/${item.book.id}`} className="cart-cover-link">
                    <BookCover book={item.book} className="book-cover cart-cover" />
                  </Link>

                  <div className="cart-item-info">
                    <h2>
                      <Link to={`/books/${item.book.id}`}>{item.book.title}</Link>
                    </h2>
                    <p className="book-author">{item.book.author}</p>
                    <p className="unit-price">
                      {formatPrice(item.book.price)} each
                    </p>
                  </div>

                  <div className="quantity-control" aria-label={`Quantity for ${item.book.title}`}>
                    <button
                      type="button"
                      className="quantity-button"
                      aria-label={`Decrease quantity of ${item.book.title}`}
                      disabled={pending || item.quantity <= 1}
                      onClick={() => changeQuantity(item, item.quantity - 1)}
                    >
                      −
                    </button>
                    <span className="quantity-value" aria-live="polite">
                      {item.quantity}
                    </span>
                    <button
                      type="button"
                      className="quantity-button"
                      aria-label={`Increase quantity of ${item.book.title}`}
                      disabled={
                        pending || item.quantity >= item.book.stock_quantity
                      }
                      onClick={() => changeQuantity(item, item.quantity + 1)}
                    >
                      +
                    </button>
                  </div>

                  <p className="line-total">{formatPrice(item.subtotal)}</p>

                  <button
                    type="button"
                    className="button-link danger"
                    disabled={pending}
                    onClick={() => removeItem(item.id)}
                  >
                    Remove
                  </button>
                </article>
              );
            })}
          </div>

          <aside className="cart-summary" aria-labelledby="summary-heading">
            <h2 id="summary-heading">Order summary</h2>
            <div className="summary-row">
              <span>Items</span>
              <span>{cart.item_count}</span>
            </div>
            <div className="summary-row total">
              <span>Total</span>
              <strong>{formatPrice(cart.total)}</strong>
            </div>
            <button
              type="button"
              className="button primary"
              onClick={() => navigate("/checkout")}
            >
              Proceed to checkout
            </button>
            <Link className="button secondary" to="/books">
              Continue shopping
            </Link>
          </aside>
        </div>
      )}
    </section>
  );
}

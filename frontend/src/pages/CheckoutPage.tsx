import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  useCart,
  useCartAvailability,
  usePayOrder,
  usePlaceOrder,
} from "../hooks/useBookStore";
import { ApiError } from "../api";
import { formatPrice } from "../format";
import type { AvailabilityProblem } from "../types";

interface CardForm {
  cardNumber: string;
  cvc: string;
  expiryMonth: string;
  expiryYear: string;
}

const EMPTY_FORM: CardForm = {
  cardNumber: "",
  cvc: "",
  expiryMonth: "",
  expiryYear: "",
};

function formatCardError(error: unknown): string {
  if (error instanceof ApiError) {
    const problems = error.body.availability as
      | AvailabilityProblem[]
      | undefined;
    if (problems && problems.length > 0) {
      return problems.map((problem) => problem.reason).join(" ");
    }
    return error.message;
  }
  return error instanceof Error ? error.message : "Payment failed.";
}

export default function CheckoutPage() {
  const navigate = useNavigate();

  const cartQuery = useCart();
  const availabilityQuery = useCartAvailability();
  const placeOrderMutation = usePlaceOrder();
  const payMutation = usePayOrder();

  const [form, setForm] = useState<CardForm>(EMPTY_FORM);
  const [orderId, setOrderId] = useState<number | null>(null);
  const [error, setError] = useState("");

  const cart = cartQuery.data?.cart;
  const availability = availabilityQuery.data;
  const busy = placeOrderMutation.isPending || payMutation.isPending;

  const availabilityProblems = availability && !availability.available
    ? availability.problems
    : [];

  function updateField(name: keyof CardForm, value: string) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError("");

    try {
      let currentOrderId = orderId;

      if (currentOrderId === null) {
        // Step 1: place the order from the cart (runs the availability
        // check server-side before the order is created).
        const placed = await placeOrderMutation.mutateAsync();
        currentOrderId = placed.order.id;
        setOrderId(currentOrderId);
      }

      // Step 2: pay the placed order. A declined payment leaves the
      // order pending, so submitting again retries the same order.
      await payMutation.mutateAsync({
        order_id: currentOrderId,
        card_number: form.cardNumber,
        cvc: form.cvc,
        expiry_month: Number(form.expiryMonth),
        expiry_year: Number(form.expiryYear),
      });

      navigate(`/orders/${currentOrderId}/confirmation`);
    } catch (requestError) {
      setError(formatCardError(requestError));
    }
  }

  if (cartQuery.isPending) {
    return <div className="status-panel">Loading checkout...</div>;
  }

  if (cartQuery.isError) {
    return (
      <div className="status-panel">
        <h1>Could not load checkout</h1>
        <p>{cartQuery.error.message}</p>
        <Link className="text-link" to="/cart">
          Back to the cart
        </Link>
      </div>
    );
  }

  if (!cart || cart.items.length === 0) {
    return (
      <div className="status-panel">
        <h1>Nothing to check out</h1>
        <p>Your cart is empty. Add a book before placing an order.</p>
        <Link className="button primary" to="/books">
          Browse books
        </Link>
      </div>
    );
  }

  return (
    <section className="checkout-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Checkout</p>
          <h1>Place your order</h1>
          <p className="page-intro">
            Availability is verified before the order is placed, and payment
            confirms it. Failed payments never appear as successful orders.
          </p>
        </div>
      </header>

      {error ? (
        <div className="alert error" role="alert">
          {error}
        </div>
      ) : null}

      {availabilityProblems.length > 0 ? (
        <div className="alert error" role="alert">
          <strong>Some books are no longer available:</strong>
          <ul>
            {availabilityProblems.map((problem, index) => (
              <li key={index}>{problem.reason}</li>
            ))}
          </ul>
          <p>Update your cart before placing the order.</p>
        </div>
      ) : null}

      <div className="checkout-layout">
        <form className="checkout-form" onSubmit={handleSubmit}>
          <h2>Card payment</h2>
          <p className="muted">
            {orderId === null
              ? "Your order is placed and then paid in one step."
              : `Retrying payment for order #${orderId}.`}
          </p>

          <div className="field">
            <label htmlFor="card_number">Card number</label>
            <input
              id="card_number"
              name="card_number"
              type="text"
              inputMode="numeric"
              autoComplete="cc-number"
              placeholder="4242 4242 4242 4242"
              value={form.cardNumber}
              onChange={(event) =>
                updateField("cardNumber", event.target.value)
              }
              required
            />
          </div>

          <div className="field-row">
            <div className="field">
              <label htmlFor="expiry_month">Expiry month</label>
              <input
                id="expiry_month"
                name="expiry_month"
                type="number"
                min="1"
                max="12"
                placeholder="MM"
                value={form.expiryMonth}
                onChange={(event) =>
                  updateField("expiryMonth", event.target.value)
                }
                required
              />
            </div>
            <div className="field">
              <label htmlFor="expiry_year">Expiry year</label>
              <input
                id="expiry_year"
                name="expiry_year"
                type="number"
                min="2026"
                placeholder="YYYY"
                value={form.expiryYear}
                onChange={(event) =>
                  updateField("expiryYear", event.target.value)
                }
                required
              />
            </div>
            <div className="field">
              <label htmlFor="cvc">CVC</label>
              <input
                id="cvc"
                name="cvc"
                type="text"
                inputMode="numeric"
                autoComplete="cc-csc"
                placeholder="123"
                value={form.cvc}
                onChange={(event) => updateField("cvc", event.target.value)}
                required
              />
            </div>
          </div>

          <button
            type="submit"
            className="button primary"
            disabled={busy || availabilityProblems.length > 0}
          >
            {busy
              ? "Processing..."
              : orderId === null
                ? `Place order and pay ${formatPrice(cart.total)}`
                : "Retry payment"}
          </button>
        </form>

        <aside className="cart-summary" aria-labelledby="checkout-summary">
          <h2 id="checkout-summary">Order summary</h2>
          <ul className="summary-items">
            {cart.items.map((item) => (
              <li key={item.id} className="summary-item">
                <span>
                  {item.book.title} × {item.quantity}
                </span>
                <span>{formatPrice(item.subtotal)}</span>
              </li>
            ))}
          </ul>
          <div className="summary-row">
            <span>Items</span>
            <span>{cart.item_count}</span>
          </div>
          <div className="summary-row total">
            <span>Total</span>
            <strong>{formatPrice(cart.total)}</strong>
          </div>
          <Link className="button secondary" to="/cart">
            Back to the cart
          </Link>
        </aside>
      </div>
    </section>
  );
}

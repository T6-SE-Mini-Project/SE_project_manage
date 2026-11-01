import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { getOrder } from "../api";
import { formatPrice } from "../format";

function formatOrderDate(value) {
  if (!value) {
    return "Just now";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function OrderConfirmationPage() {
  const { orderId } = useParams();
  const location = useLocation();
  const [order, setOrder] = useState(location.state?.order || null);
  const [addressSaved, setAddressSaved] = useState(
    Boolean(location.state?.addressSaved),
  );
  const [authenticated, setAuthenticated] = useState(
    Boolean(location.state?.authenticated),
  );
  const [loading, setLoading] = useState(!location.state?.order);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    getOrder(orderId)
      .then((data) => {
        if (active) {
          setOrder(data.order);
        }
      })
      .catch((requestError) => {
        if (active) {
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
  }, [orderId]);

  if (loading && !order) {
    return <div className="status-panel">Loading your order...</div>;
  }

  if (!order) {
    return (
      <div className="status-panel">
        <h1>Order not found</h1>
        <p>{error || "This order is not available in your session."}</p>
        <Link className="text-link" to="/books">
          Back to the catalogue
        </Link>
      </div>
    );
  }

  const address = order.billing_address;

  return (
    <section className="confirmation-page">
      <div className="success-panel">
        <span className="success-badge" aria-hidden="true">
          ✓
        </span>
        <p className="eyebrow">Order created</p>
        <h1>Thank you, {address.full_name.split(" ")[0]}.</h1>
        <p className="page-intro">
          Order <strong>#{order.short_reference}</strong> was placed on{" "}
          {formatOrderDate(order.created_at)} and is now marked{" "}
          <strong>{order.status_label}</strong>.
        </p>
        <p className="notice">
          No payment has been taken. Payment integration is not part of this
          milestone, so this order is awaiting a future payment step. No card
          or banking details were collected or stored.
        </p>
        {addressSaved ? (
          <div className="alert success" role="status">
            Billing address saved to your account for future orders.
          </div>
        ) : (
          <div className="alert neutral" role="status">
            {authenticated
              ? "This billing address is attached to this order only."
              : "Guest order: this billing address is attached to this order only."}
          </div>
        )}
      </div>

      <div className="confirmation-grid">
        <section className="checkout-card">
          <h2>Billing address</h2>
          <address className="address-block">
            <strong>{address.full_name}</strong>
            <span>{address.address_line1}</span>
            {address.address_line2 ? (
              <span>{address.address_line2}</span>
            ) : null}
            <span>
              {address.city}, {address.state} {address.postal_code}
            </span>
            <span>{address.country}</span>
            <span>{address.phone_number}</span>
            <span>{address.email}</span>
          </address>
        </section>

        <aside className="cart-summary checkout-summary">
          <h2>Order total</h2>
          <ul className="checkout-items">
            {order.items.map((item) => (
              <li key={item.id}>
                <span>
                  {item.quantity} × {item.title}
                </span>
                <span>{formatPrice(item.subtotal)}</span>
              </li>
            ))}
          </ul>
          <div className="summary-row">
            <span>Items</span>
            <span>{order.item_count}</span>
          </div>
          <div className="summary-row total">
            <span>Total</span>
            <strong>{formatPrice(order.total)}</strong>
          </div>
          <Link className="button primary" to="/books">
            Continue shopping
          </Link>
          <Link className="button secondary" to="/cart">
            View cart
          </Link>
        </aside>
      </div>
    </section>
  );
}

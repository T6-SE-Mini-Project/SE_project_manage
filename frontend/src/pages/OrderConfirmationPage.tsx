import { Link, useParams } from "react-router-dom";

import { useOrder } from "../hooks/useBookStore";
import { formatDate, formatPrice } from "../format";

export default function OrderConfirmationPage() {
  const { orderId } = useParams();

  const orderQuery = useOrder(orderId);
  const order = orderQuery.data?.order;

  if (orderQuery.isPending) {
    return <div className="status-panel">Loading your order...</div>;
  }

  if (orderQuery.isError || !order) {
    return (
      <div className="status-panel">
        <h1>Order not found</h1>
        <p>
          {orderQuery.error?.message ||
            "The requested order is not available for this session."}
        </p>
        <Link className="text-link" to="/books">
          Back to the catalogue
        </Link>
      </div>
    );
  }

  if (!order.is_confirmed) {
    return (
      <div className="status-panel">
        <h1>Order #{order.id} is awaiting payment</h1>
        <p>
          This order has been placed but not paid yet. Return to checkout to
          complete the payment.
        </p>
        <Link className="button primary" to="/checkout">
          Go to checkout
        </Link>
      </div>
    );
  }

  return (
    <section className="confirmation-page">
      <div className="confirmation-panel">
        <p className="confirmation-icon" aria-hidden="true">
          ✓
        </p>
        <p className="eyebrow">Order confirmed</p>
        <h1>Thank you for your purchase!</h1>
        <p className="page-intro">
          Order #{order.id} was placed on {formatDate(order.created_at.slice(0, 10))}{" "}
          and payment succeeded. A confirmation with the details below is
          available from this page.
        </p>

        <div className="confirmation-items">
          {order.items.map((item) => (
            <div className="summary-item" key={item.id}>
              <span>
                {item.title} × {item.quantity}
              </span>
              <span>{formatPrice(item.line_total)}</span>
            </div>
          ))}
        </div>

        <div className="summary-row total">
          <span>Total paid</span>
          <strong>{formatPrice(order.total_amount)}</strong>
        </div>

        <div className="confirmation-actions">
          <Link className="button primary" to="/books">
            Continue shopping
          </Link>
        </div>
      </div>
    </section>
  );
}

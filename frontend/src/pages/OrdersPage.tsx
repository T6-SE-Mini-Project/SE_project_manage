/**
 * Order history and cancellation (issue #10, OBS-F-014 and OBS-F-015).
 *
 * Lists the customer's orders with the information for each one, and
 * offers cancellation only for orders the server reports as eligible.
 */
import { useState } from "react";
import { Link } from "react-router-dom";

import OrderStatusBadge from "../components/OrderStatusBadge";
import { useCancelOrder, useOrders } from "../hooks/useBookStore";
import { useSession } from "../hooks/useAuth";
import { ApiError } from "../api";
import { errorMessage } from "../errors";
import { formatDateTime, formatPrice } from "../format";
import type { Order } from "../types";

export default function OrdersPage() {
  const { isAuthenticated } = useSession();
  const ordersQuery = useOrders();
  const cancelMutation = useCancelOrder();

  const [confirming, setConfirming] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [failure, setFailure] = useState("");
  const [notice, setNotice] = useState("");

  const orders = ordersQuery.data?.orders ?? [];

  async function handleCancel(order: Order) {
    setFailure("");
    setNotice("");

    try {
      const result = await cancelMutation.mutateAsync({
        orderId: order.id,
        reason,
      });
      setConfirming(null);
      setReason("");
      setNotice(
        result.order.refund_due
          ? `Order #${order.id} has been cancelled. A refund is due for the ` +
            "amount already paid."
          : `Order #${order.id} has been cancelled.`,
      );
    } catch (error) {
      // A 409 means the order is no longer eligible, for example because
      // it shipped since the page was loaded.
      setFailure(
        error instanceof ApiError && error.status === 409
          ? error.message
          : errorMessage(error, "The order could not be cancelled."),
      );
      void ordersQuery.refetch();
    }
  }

  if (ordersQuery.isPending) {
    return <div className="status-panel">Loading your orders...</div>;
  }

  if (ordersQuery.isError) {
    return (
      <div className="status-panel">
        <h1>Could not load your orders</h1>
        <p>{errorMessage(ordersQuery.error, "An unexpected error occurred.")}</p>
      </div>
    );
  }

  return (
    <section className="orders-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Your account</p>
          <h1>Order history</h1>
          <p className="page-intro">
            {isAuthenticated
              ? "Every order on your account, newest first."
              : "Orders placed in this browser session. Log in to keep your " +
                "order history with your account."}
          </p>
        </div>
      </header>

      {notice ? (
        <div className="alert success" role="status">
          {notice}
        </div>
      ) : null}

      {failure ? (
        <div className="alert error" role="alert">
          {failure}
        </div>
      ) : null}

      {orders.length === 0 ? (
        <div className="status-panel">
          <h2>No orders yet</h2>
          <p>Orders you place will appear here.</p>
          <Link className="button primary" to="/books">
            Browse books
          </Link>
        </div>
      ) : (
        <ul className="order-list">
          {orders.map((order) => (
            <li key={order.id} className="order-card">
              <header className="order-card-header">
                <div>
                  <h2>Order #{order.id}</h2>
                  <p className="muted">
                    Placed {formatDateTime(order.created_at)}
                    {order.is_paid
                      ? ` · paid ${formatDateTime(order.paid_at)}`
                      : ""}
                  </p>
                </div>
                <OrderStatusBadge
                  status={order.status}
                  label={order.status_display}
                />
              </header>

              <ul className="summary-items">
                {order.items.map((item) => (
                  <li key={item.id} className="summary-item">
                    <span>
                      <Link className="text-link" to={`/books/${item.book_id}`}>
                        {item.title}
                      </Link>{" "}
                      × {item.quantity}
                    </span>
                    <span>{formatPrice(item.line_total)}</span>
                  </li>
                ))}
              </ul>

              <div className="summary-row total">
                <span>
                  {order.item_count} item{order.item_count === 1 ? "" : "s"}
                </span>
                <strong>{formatPrice(order.total_amount)}</strong>
              </div>

              {order.is_cancelled ? (
                <p className="muted">
                  Cancelled {formatDateTime(order.cancelled_at)} ·{" "}
                  {order.cancellation_reason}
                  {order.refund_due ? " · refund due" : ""}
                </p>
              ) : null}

              <div className="order-card-actions">
                {!order.is_paid && !order.is_cancelled ? (
                  <Link className="button primary" to="/checkout">
                    Complete payment
                  </Link>
                ) : null}

                {order.is_confirmed ? (
                  <Link
                    className="button secondary"
                    to={`/orders/${order.id}/confirmation`}
                  >
                    View confirmation
                  </Link>
                ) : null}

                {order.is_cancellable ? (
                  confirming === order.id ? (
                    <div className="cancel-confirm">
                      <label htmlFor={`reason-${order.id}`}>
                        Reason (optional)
                      </label>
                      <input
                        id={`reason-${order.id}`}
                        type="text"
                        maxLength={255}
                        value={reason}
                        onChange={(event) => setReason(event.target.value)}
                      />
                      <div className="form-actions">
                        <button
                          type="button"
                          className="button danger"
                          onClick={() => handleCancel(order)}
                          disabled={cancelMutation.isPending}
                        >
                          {cancelMutation.isPending
                            ? "Cancelling..."
                            : "Confirm cancellation"}
                        </button>
                        <button
                          type="button"
                          className="button secondary"
                          onClick={() => {
                            setConfirming(null);
                            setReason("");
                          }}
                          disabled={cancelMutation.isPending}
                        >
                          Keep order
                        </button>
                      </div>
                      {order.is_paid ? (
                        <p className="muted">
                          This order has been paid, so cancelling it means a
                          refund is due.
                        </p>
                      ) : null}
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="button danger"
                      onClick={() => {
                        setConfirming(order.id);
                        setFailure("");
                        setNotice("");
                      }}
                    >
                      Cancel order
                    </button>
                  )
                ) : !order.is_cancelled ? (
                  <p className="muted">
                    This order can no longer be cancelled because it has
                    already been {order.status_display.toLowerCase()}.
                  </p>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

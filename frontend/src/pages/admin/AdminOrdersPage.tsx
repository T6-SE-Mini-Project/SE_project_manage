/**
 * Administrator order management (issue #12, OBS-F-018).
 *
 * Lists every customer's orders and offers only the status transitions
 * the server reports as allowed, so the UI cannot suggest a change that
 * would be refused.
 */
import { useState } from "react";

import OrderStatusBadge from "../../components/OrderStatusBadge";
import {
  useAdminCancelOrder,
  useAdminOrders,
  useSetOrderStatus,
} from "../../hooks/useAdmin";
import { errorMessage } from "../../errors";
import { formatDateTime, formatPrice } from "../../format";
import type { OrderStatus, OrderSummary } from "../../types";

const STATUS_FILTERS: { value: string; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "PENDING", label: "Pending payment" },
  { value: "CONFIRMED", label: "Confirmed" },
  { value: "PROCESSING", label: "Processing" },
  { value: "SHIPPED", label: "Shipped" },
  { value: "DELIVERED", label: "Delivered" },
  { value: "CANCELLED", label: "Cancelled" },
];

const STATUS_LABELS: Record<OrderStatus, string> = {
  PENDING: "Pending payment",
  CONFIRMED: "Confirmed",
  PROCESSING: "Processing",
  SHIPPED: "Shipped",
  DELIVERED: "Delivered",
  CANCELLED: "Cancelled",
};

export default function AdminOrdersPage() {
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");

  const ordersQuery = useAdminOrders({
    status: status || undefined,
    q: search || undefined,
  });
  const statusMutation = useSetOrderStatus();
  const cancelMutation = useAdminCancelOrder();

  const [notice, setNotice] = useState("");
  const [failure, setFailure] = useState("");

  const orders = ordersQuery.data?.orders ?? [];
  const allowed = ordersQuery.data?.allowed_transitions ?? {};
  const busy = statusMutation.isPending || cancelMutation.isPending;

  async function advance(order: OrderSummary, next: OrderStatus) {
    setNotice("");
    setFailure("");

    try {
      await statusMutation.mutateAsync({ orderId: order.id, status: next });
      setNotice(
        `Order #${order.id} is now ${STATUS_LABELS[next].toLowerCase()}.`,
      );
    } catch (error) {
      setFailure(errorMessage(error, "The order status could not be changed."));
    }
  }

  async function cancel(order: OrderSummary) {
    setNotice("");
    setFailure("");

    try {
      await cancelMutation.mutateAsync({
        orderId: order.id,
        reason: "Cancelled by an administrator.",
      });
      setNotice(
        `Order #${order.id} has been cancelled and its stock released.`,
      );
    } catch (error) {
      setFailure(errorMessage(error, "The order could not be cancelled."));
    }
  }

  return (
    <div className="admin-section">
      <div className="admin-toolbar">
        <div className="field">
          <label htmlFor="order-status">Status</label>
          <select
            id="order-status"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            {STATUS_FILTERS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="order-search">Search customer or order id</label>
          <input
            id="order-search"
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
      </div>

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

      <h2>Orders ({ordersQuery.data?.count ?? 0})</h2>

      {ordersQuery.isPending ? (
        <p className="muted">Loading orders...</p>
      ) : ordersQuery.isError ? (
        <p className="feedback error">
          {errorMessage(ordersQuery.error, "Orders could not be loaded.")}
        </p>
      ) : orders.length === 0 ? (
        <p className="muted">No orders match the current filters.</p>
      ) : (
        <div className="table-scroll">
          <table className="admin-table">
            <thead>
              <tr>
                <th scope="col">Order</th>
                <th scope="col">Customer</th>
                <th scope="col">Placed</th>
                <th scope="col">Items</th>
                <th scope="col">Total</th>
                <th scope="col">Status</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => {
                const next = (allowed[order.status] ?? []) as OrderStatus[];

                return (
                  <tr key={order.id}>
                    <td>#{order.id}</td>
                    <td>
                      {order.customer
                        ? `${order.customer.username} (${order.customer.email})`
                        : "Guest"}
                    </td>
                    <td>{formatDateTime(order.created_at)}</td>
                    <td>{order.item_count}</td>
                    <td>{formatPrice(order.total_amount)}</td>
                    <td>
                      <OrderStatusBadge
                        status={order.status}
                        label={order.status_display}
                      />
                      {order.refund_due ? (
                        <span className="badge warning">refund due</span>
                      ) : null}
                    </td>
                    <td className="table-actions">
                      {next.map((target) => (
                        <button
                          key={target}
                          type="button"
                          className="button secondary small"
                          onClick={() => advance(order, target)}
                          disabled={busy}
                        >
                          Mark {STATUS_LABELS[target].toLowerCase()}
                        </button>
                      ))}
                      {order.is_cancellable ? (
                        <button
                          type="button"
                          className="button danger small"
                          onClick={() => cancel(order)}
                          disabled={busy}
                        >
                          Cancel
                        </button>
                      ) : null}
                      {next.length === 0 && !order.is_cancellable ? (
                        <span className="muted">No actions available</span>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

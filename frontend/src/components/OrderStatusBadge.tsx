import type { OrderStatus } from "../types";

/** Maps an order status to the badge class that colours it. */
const TONE: Record<OrderStatus, string> = {
  PENDING: "warning",
  CONFIRMED: "success",
  PROCESSING: "info",
  SHIPPED: "info",
  DELIVERED: "success",
  CANCELLED: "muted",
};

interface OrderStatusBadgeProps {
  status: OrderStatus;
  /** The server-rendered label, e.g. "Pending payment". */
  label?: string;
}

export default function OrderStatusBadge({
  status,
  label,
}: OrderStatusBadgeProps) {
  return (
    <span className={`badge ${TONE[status] ?? "muted"}`}>
      {label ?? status}
    </span>
  );
}

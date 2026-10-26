/**
 * Administrator customer management (issue #24).
 *
 * Accounts are deactivated rather than deleted: orders reference the
 * customer, so deactivating blocks new logins while keeping the history.
 */
import { useState } from "react";

import {
  useCustomers,
  useSetCustomerActive,
} from "../../hooks/useAdmin";
import { useSession } from "../../hooks/useAuth";
import { errorMessage } from "../../errors";
import { formatDateTime, formatPrice } from "../../format";
import type { Customer } from "../../types";

export default function AdminCustomersPage() {
  const { user } = useSession();

  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");

  const customersQuery = useCustomers({
    q: search || undefined,
    status: status || undefined,
  });
  const statusMutation = useSetCustomerActive();

  const [notice, setNotice] = useState("");
  const [failure, setFailure] = useState("");

  const customers = customersQuery.data?.customers ?? [];

  async function toggle(customer: Customer) {
    setNotice("");
    setFailure("");

    try {
      await statusMutation.mutateAsync({
        customerId: customer.id,
        isActive: !customer.is_active,
      });
      setNotice(
        customer.is_active
          ? `${customer.username} has been deactivated and can no longer log in.`
          : `${customer.username} has been reactivated.`,
      );
    } catch (error) {
      setFailure(
        errorMessage(error, "The account status could not be changed."),
      );
    }
  }

  return (
    <div className="admin-section">
      <div className="admin-toolbar">
        <div className="field">
          <label htmlFor="customer-search">Search username or email</label>
          <input
            id="customer-search"
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="customer-status">Account status</label>
          <select
            id="customer-status"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">All accounts</option>
            <option value="active">Active</option>
            <option value="inactive">Deactivated</option>
          </select>
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

      <h2>Customers ({customersQuery.data?.count ?? 0})</h2>

      {customersQuery.isPending ? (
        <p className="muted">Loading customer accounts...</p>
      ) : customersQuery.isError ? (
        <p className="feedback error">
          {errorMessage(
            customersQuery.error,
            "Customer accounts could not be loaded.",
          )}
        </p>
      ) : customers.length === 0 ? (
        <p className="muted">No accounts match the current filters.</p>
      ) : (
        <div className="table-scroll">
          <table className="admin-table">
            <thead>
              <tr>
                <th scope="col">Username</th>
                <th scope="col">Email</th>
                <th scope="col">Joined</th>
                <th scope="col">Orders</th>
                <th scope="col">Cancelled</th>
                <th scope="col">Total spent</th>
                <th scope="col">Last order</th>
                <th scope="col">Status</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {customers.map((customer) => {
                const isSelf = customer.id === user?.id;

                return (
                  <tr key={customer.id}>
                    <td>
                      {customer.username}
                      {customer.is_staff ? (
                        <span className="badge info">admin</span>
                      ) : null}
                    </td>
                    <td>{customer.email || "—"}</td>
                    <td>{formatDateTime(customer.date_joined)}</td>
                    <td>{customer.order_count}</td>
                    <td>{customer.cancelled_order_count}</td>
                    <td>{formatPrice(customer.total_spent)}</td>
                    <td>
                      {customer.last_order_at
                        ? formatDateTime(customer.last_order_at)
                        : "—"}
                    </td>
                    <td>
                      <span
                        className={
                          customer.is_active ? "badge success" : "badge muted"
                        }
                      >
                        {customer.is_active ? "Active" : "Deactivated"}
                      </span>
                    </td>
                    <td className="table-actions">
                      {isSelf ? (
                        <span className="muted">Your account</span>
                      ) : customer.is_staff && customer.is_active ? (
                        <span className="muted">Administrator</span>
                      ) : (
                        <button
                          type="button"
                          className={
                            customer.is_active
                              ? "button danger small"
                              : "button secondary small"
                          }
                          onClick={() => toggle(customer)}
                          disabled={statusMutation.isPending}
                        >
                          {customer.is_active ? "Deactivate" : "Reactivate"}
                        </button>
                      )}
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

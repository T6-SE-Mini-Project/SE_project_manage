/**
 * Sales reports and backup inspection (issues #24 and #18).
 *
 * The headline figures are stat tiles rather than a chart: a single
 * number reads better as a number. The status breakdown and best sellers
 * are magnitude comparisons, and the daily series is a trend over time.
 */
import { useState } from "react";

import MagnitudeBars from "../../components/MagnitudeBars";
import RevenueTrend from "../../components/RevenueTrend";
import { useBackups, useSalesReport } from "../../hooks/useAdmin";
import { errorMessage } from "../../errors";
import { formatDateTime, formatPrice } from "../../format";
import type { OrderStatus } from "../../types";

const STATUS_LABELS: Record<OrderStatus, string> = {
  PENDING: "Pending payment",
  CONFIRMED: "Confirmed",
  PROCESSING: "Processing",
  SHIPPED: "Shipped",
  DELIVERED: "Delivered",
  CANCELLED: "Cancelled",
};

export default function AdminReportsPage() {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const reportQuery = useSalesReport({
    start: start || undefined,
    end: end || undefined,
  });
  const backupsQuery = useBackups();

  const report = reportQuery.data?.report;
  const backups = backupsQuery.data;

  return (
    <div className="admin-section">
      <form
        className="admin-toolbar"
        onSubmit={(event) => event.preventDefault()}
      >
        <div className="field">
          <label htmlFor="report-start">From</label>
          <input
            id="report-start"
            type="date"
            value={start}
            onChange={(event) => setStart(event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="report-end">To</label>
          <input
            id="report-end"
            type="date"
            value={end}
            onChange={(event) => setEnd(event.target.value)}
          />
        </div>
        {start || end ? (
          <button
            type="button"
            className="button secondary"
            onClick={() => {
              setStart("");
              setEnd("");
            }}
          >
            Clear period
          </button>
        ) : null}
      </form>

      {reportQuery.isPending ? (
        <p className="muted">Generating the sales report...</p>
      ) : reportQuery.isError ? (
        <div className="alert error" role="alert">
          {errorMessage(
            reportQuery.error,
            "The sales report could not be generated.",
          )}
        </div>
      ) : report ? (
        <>
          <h2>
            Sales
            {report.period.start || report.period.end
              ? ` from ${report.period.start ?? "the beginning"} to ${
                  report.period.end ?? "today"
                }`
              : " (all time)"}
          </h2>

          <div className="stat-grid">
            <div className="stat-tile">
              <p className="stat-label">Revenue</p>
              <p className="stat-value">{formatPrice(report.revenue.total)}</p>
            </div>
            <div className="stat-tile">
              <p className="stat-label">Paid orders</p>
              <p className="stat-value">{report.revenue.order_count}</p>
            </div>
            <div className="stat-tile">
              <p className="stat-label">Average order</p>
              <p className="stat-value">
                {formatPrice(report.revenue.average_order_value)}
              </p>
            </div>
            <div className="stat-tile">
              <p className="stat-label">Books sold</p>
              <p className="stat-value">{report.revenue.items_sold}</p>
            </div>
          </div>

          <p className="muted">
            Revenue counts orders with status{" "}
            {report.revenue.counted_statuses
              .map((status) => STATUS_LABELS[status].toLowerCase())
              .join(", ")}
            . Pending and cancelled orders are reported separately below.
          </p>

          <section className="report-block">
            <h3>Revenue over time</h3>
            <RevenueTrend points={report.daily} />
            {report.daily.length > 0 ? (
              <details>
                <summary>View the daily figures as a table</summary>
                <div className="table-scroll">
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th scope="col">Date</th>
                        <th scope="col">Orders</th>
                        <th scope="col">Revenue</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.daily.map((day) => (
                        <tr key={day.date}>
                          <td>{day.date}</td>
                          <td>{day.order_count}</td>
                          <td>{formatPrice(day.revenue)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            ) : null}
          </section>

          <section className="report-block">
            <h3>Orders by status</h3>
            <MagnitudeBars
              caption="Number of orders in each status"
              rows={(
                Object.keys(report.orders_by_status) as OrderStatus[]
              ).map((status) => ({
                key: status,
                label: STATUS_LABELS[status] ?? status,
                value: report.orders_by_status[status],
              }))}
            />
          </section>

          <section className="report-block">
            <h3>Best-selling books</h3>
            {report.top_books.length === 0 ? (
              <p className="muted">No books were sold in this period.</p>
            ) : (
              <>
                <MagnitudeBars
                  caption="Copies sold per title"
                  rows={report.top_books.map((book) => ({
                    key: String(book.book_id),
                    label: book.title,
                    value: book.quantity_sold,
                    display: `${book.quantity_sold} sold`,
                  }))}
                />
                <div className="table-scroll">
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th scope="col">Title</th>
                        <th scope="col">Copies sold</th>
                        <th scope="col">Revenue</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.top_books.map((book) => (
                        <tr key={book.book_id}>
                          <td>{book.title}</td>
                          <td>{book.quantity_sold}</td>
                          <td>{formatPrice(book.revenue)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </section>

          <p className="muted">
            Generated {formatDateTime(report.generated_at)}.
          </p>
        </>
      ) : null}

      <section className="report-block">
        <h3>Order and inventory backups</h3>
        <p className="muted">
          Backups are written by a scheduled job and must succeed at least
          once every 24 hours.
        </p>

        {backupsQuery.isPending ? (
          <p className="muted">Loading backup records...</p>
        ) : backupsQuery.isError ? (
          <p className="feedback error">
            {errorMessage(
              backupsQuery.error,
              "Backup records could not be loaded.",
            )}
          </p>
        ) : backups ? (
          <>
            <p
              className={
                backups.freshness.fresh ? "alert success" : "alert error"
              }
              role="status"
            >
              {backups.freshness.detail}
            </p>

            {backups.runs.length === 0 ? (
              <p className="muted">
                No backup has run yet. Schedule
                <code> manage.py backup_data --trigger scheduled </code>
                to start.
              </p>
            ) : (
              <div className="table-scroll">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th scope="col">Run</th>
                      <th scope="col">Started</th>
                      <th scope="col">Status</th>
                      <th scope="col">Trigger</th>
                      <th scope="col">Records</th>
                      <th scope="col">Size</th>
                    </tr>
                  </thead>
                  <tbody>
                    {backups.runs.map((run) => (
                      <tr key={run.id}>
                        <td>#{run.id}</td>
                        <td>{formatDateTime(run.started_at)}</td>
                        <td>
                          <span
                            className={
                              run.status === "SUCCESS"
                                ? "badge success"
                                : "badge muted"
                            }
                          >
                            {run.status === "SUCCESS" ? "Success" : "Failed"}
                          </span>
                          {run.error_message ? (
                            <p className="muted">{run.error_message}</p>
                          ) : null}
                        </td>
                        <td>{run.trigger === "SCHEDULED" ? "Scheduled" : "Manual"}</td>
                        <td>{run.total_records}</td>
                        <td>{Math.round(run.size_bytes / 1024)} KB</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        ) : null}
      </section>
    </div>
  );
}

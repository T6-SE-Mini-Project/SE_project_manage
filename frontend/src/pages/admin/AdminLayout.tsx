/** Shared shell and sub-navigation for the administrator screens. */
import { NavLink, Outlet } from "react-router-dom";

const SECTIONS = [
  { to: "/admin/books", label: "Catalogue" },
  { to: "/admin/orders", label: "Orders" },
  { to: "/admin/customers", label: "Customers" },
  { to: "/admin/reports", label: "Sales reports" },
];

export default function AdminLayout() {
  return (
    <section className="admin-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Administration</p>
          <h1>Store management</h1>
          <p className="page-intro">
            Manage the book catalogue, process orders, review customer
            accounts and generate sales reports.
          </p>
        </div>
      </header>

      <nav className="admin-nav" aria-label="Administration sections">
        {SECTIONS.map((section) => (
          <NavLink
            key={section.to}
            to={section.to}
            className={({ isActive }) =>
              isActive ? "nav-link active" : "nav-link"
            }
          >
            {section.label}
          </NavLink>
        ))}
      </nav>

      <Outlet />
    </section>
  );
}

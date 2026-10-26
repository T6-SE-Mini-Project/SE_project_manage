import { Link, NavLink, Outlet } from "react-router-dom";

export default function Layout() {
  return (
    <div className="app-shell">
      <header className="site-header">
        <Link className="brand" to="/books">
          <span className="brand-mark" aria-hidden="true">
            OBS
          </span>
          <span>Online Book Store</span>
        </Link>

        <nav className="site-nav" aria-label="Main navigation">
          <NavLink
            to="/books"
            className={({ isActive }) =>
              isActive ? "nav-link active" : "nav-link"
            }
          >
            Books
          </NavLink>
          <NavLink
            to="/cart"
            className={({ isActive }) =>
              isActive ? "nav-link active" : "nav-link"
            }
          >
            Cart
          </NavLink>
        </nav>
      </header>

      <main className="page">
        <Outlet />
      </main>

      <footer className="site-footer">
        <p>Online Book Store · Browse, discover and collect.</p>
      </footer>
    </div>
  );
}

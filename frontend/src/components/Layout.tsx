import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

import { useLogout, useSession } from "../hooks/useAuth";
import { useCart } from "../hooks/useBookStore";

function navClass({ isActive }: { isActive: boolean }) {
  return isActive ? "nav-link active" : "nav-link";
}

export default function Layout() {
  const navigate = useNavigate();
  const { user, isAuthenticated, isStaff } = useSession();
  const logoutMutation = useLogout();
  const cartQuery = useCart();

  const itemCount = cartQuery.data?.cart.item_count ?? 0;

  async function handleLogout() {
    await logoutMutation.mutateAsync(undefined);
    navigate("/books");
  }

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
          <NavLink to="/books" className={navClass}>
            Books
          </NavLink>
          <NavLink to="/cart" className={navClass}>
            Cart
            {itemCount > 0 ? (
              <span className="cart-count" aria-label={`${itemCount} items`}>
                {itemCount}
              </span>
            ) : null}
          </NavLink>
          <NavLink to="/orders" className={navClass}>
            Orders
          </NavLink>
          {isStaff ? (
            <NavLink to="/admin" className={navClass}>
              Manage
            </NavLink>
          ) : null}
        </nav>

        <div className="site-account">
          {isAuthenticated ? (
            <>
              <span className="account-name">{user?.username}</span>
              <button
                type="button"
                className="button secondary small"
                onClick={handleLogout}
                disabled={logoutMutation.isPending}
              >
                {logoutMutation.isPending ? "Logging out..." : "Log out"}
              </button>
            </>
          ) : (
            <>
              <NavLink to="/login" className={navClass}>
                Log in
              </NavLink>
              <NavLink to="/register" className={navClass}>
                Register
              </NavLink>
            </>
          )}
        </div>
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

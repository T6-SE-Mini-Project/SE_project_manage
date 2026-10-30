
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAccountName, useSession, useSignOut } from "../hooks/useAuth";
import { useCart } from "../hooks/useBookStore";

function navClass({ isActive }: { isActive: boolean }) {
  return isActive ? "nav-link active" : "nav-link";
}

export default function Layout() {
  const navigate = useNavigate();
  const { isAuthenticated, isStaff } = useSession();
  const accountName = useAccountName();
  const signOutMutation = useSignOut();
  const cartQuery = useCart();

  const itemCount = cartQuery.data?.cart.item_count ?? 0;

  async function handleLogout() {
    try {
      await signOutMutation.mutateAsync();
      navigate("/login", { replace: true });
    } catch {
      // Keep the user on the current page if logout fails.
    }
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <Link className="brand" to={isAuthenticated ? "/books" : "/login"}>
          <span className="brand-mark" aria-hidden="true">
            OBS
          </span>
          <span>Online Book Store</span>
        </Link>

        {isAuthenticated ? (
          <>
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
              <span className="account-name" title={accountName}>
                {accountName}
              </span>
              <button
                type="button"
                className="button secondary small"
                onClick={handleLogout}
                disabled={signOutMutation.isPending}
              >
                {signOutMutation.isPending ? "Logging out..." : "Log out"}
              </button>
            </div>
          </>
        ) : (
          <div className="site-account">
            <NavLink to="/login" className={navClass}>
              Log in
            </NavLink>
            <NavLink to="/register" className={navClass}>
              Create account
            </NavLink>
          </div>
        )}
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

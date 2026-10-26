/**
 * Route guard for the administrator screens (issues #12 and #24).
 *
 * This only keeps the navigation honest: the API enforces is_staff on
 * every admin request, so a customer who reaches an admin URL directly
 * still gets 403 from the server.
 */
import { Link, Navigate, Outlet, useLocation } from "react-router-dom";

import { useSession } from "../hooks/useAuth";

export default function RequireStaff() {
  const location = useLocation();
  const { isPending, isAuthenticated, isStaff } = useSession();

  if (isPending) {
    return <div className="status-panel">Checking your access...</div>;
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: location.pathname }}
      />
    );
  }

  if (!isStaff) {
    return (
      <div className="status-panel">
        <h1>Administrators only</h1>
        <p>
          This area manages the catalogue, orders, customers and sales
          reports. Your account does not have administrator access.
        </p>
        <Link className="button primary" to="/books">
          Back to the catalogue
        </Link>
      </div>
    );
  }

  return <Outlet />;
}

/**
 * The login check for every customer-facing route.
 *
 * It waits for both answers — the Firebase SDK restoring the saved
 * sign-in, and the API resolving the ID token to an account — before
 * deciding. Deciding early would bounce a signed-in customer to the
 * login page on every page load, because the SDK reports "nobody" for a
 * moment while it reads the stored credential.
 *
 * Like `RequireStaff`, this only keeps the navigation honest: every
 * protected endpoint re-checks the token server-side, so a customer who
 * types a URL directly still gets 401 from the API.
 */
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useSession } from "../hooks/useAuth";

export default function RequireAuth() {
  const location = useLocation();
  const { isPending, isAuthenticated } = useSession();

  if (isPending) {
    return <div className="status-panel">Checking your session...</div>;
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

  return <Outlet />;
}

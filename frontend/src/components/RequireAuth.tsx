
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
        to="/register"
        replace
        state={{ from: location.pathname }}
      />
    );
  }

  return <Outlet />;
}

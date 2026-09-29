import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";

/** Wraps routes that require any authenticated user. Role-specific
 * gating (e.g. admin-only pages) is layered on top per-route once those
 * pages exist — this component only checks "is anyone logged in". */
export function ProtectedRoute() {
  const { user, isInitializing } = useAuth();
  const location = useLocation();

  if (isInitializing) {
    return <FullPageSpinner />;
  }

  if (!user) {
    // Remember where they were headed so login can send them back.
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Outlet />;
}

/** Wraps /login and /register — an already-logged-in user shouldn't see
 * the login form again, they should land on the dashboard. */
export function PublicOnlyRoute() {
  const { user, isInitializing } = useAuth();

  if (isInitializing) {
    return <FullPageSpinner />;
  }

  if (user) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}

function FullPageSpinner() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="text-slate-400 text-sm">Loading…</div>
    </div>
  );
}

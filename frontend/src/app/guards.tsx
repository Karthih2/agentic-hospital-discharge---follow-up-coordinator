import { Navigate, Outlet, useLocation } from "react-router-dom";
import { ListSkeleton } from "../components/ui";
import type { Role } from "../lib/api";
import { homeFor, useAuth } from "../lib/auth";

/** Route guard. The server checks every request too; this keeps people out of screens that would only show errors. */
export function RequireRole({ roles, loginTo = "/login" }: { roles?: Role[]; loginTo?: string }) {
  const { me, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <div className="container-page py-16"><ListSkeleton /></div>;
  if (!me) return <Navigate to={loginTo} state={{ from: loc.pathname }} replace />;
  if (roles && !roles.includes(me.role)) return <Navigate to={homeFor(me.role)} replace />;
  return <Outlet />;
}

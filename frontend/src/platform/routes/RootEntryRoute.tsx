import { Navigate } from "react-router-dom";

import { useAuthStore } from "../../store/authStore";
import { isTenantSubdomain } from "../../utils/domain";
import { getAuthenticatedFallbackPath } from "../moduleRegistry";

const GuardFallback = () => (
  <div className="min-h-[70vh] flex items-center justify-center text-black text-lg" role="status" aria-live="polite">
    Betöltés…
  </div>
);

/**
 * Tenant aldomain gyökér: login / admin.
 * A fő domain „/” útvonalát a landing modul szolgálja ki.
 */
export default function RootEntryRoute() {
  const { user, loadingUser } = useAuthStore();

  if (isTenantSubdomain()) {
    if (loadingUser) return <GuardFallback />;
    if (user) return <Navigate to={getAuthenticatedFallbackPath()} replace />;
    return <Navigate to="/login" replace />;
  }

  return <Navigate to="/" replace />;
}

import { Navigate } from "react-router-dom";

import { useAuthStore } from "../../../store/authStore";
import { isTenantSubdomain } from "../../../utils/domain";
import { getAuthenticatedFallbackPath } from "../../../platform/moduleRegistry";
import LandingPage from "./LandingPage";

function GuardFallback() {
  return (
    <div className="min-h-[70vh] flex items-center justify-center text-[var(--color-foreground)] text-lg" role="status" aria-live="polite">
      Betöltés…
    </div>
  );
}

/** Fő domain: marketing landing. Tenant aldomain: login / admin. */
export default function LandingEntryRoute() {
  const { user, loadingUser } = useAuthStore();

  if (isTenantSubdomain()) {
    if (loadingUser) return <GuardFallback />;
    if (user) return <Navigate to={getAuthenticatedFallbackPath()} replace />;
    return <Navigate to="/login" replace />;
  }

  return <LandingPage />;
}

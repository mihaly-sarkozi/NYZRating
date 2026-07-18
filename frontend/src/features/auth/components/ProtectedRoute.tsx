import { Navigate, Link, useLocation } from "react-router-dom";
import { useAuthStore } from "../state/authStore";
import { useTranslation } from "../../../i18n";
import { getSafeLoginRedirect } from "../../../utils/loginRedirect";
import type { ReactNode } from "react";
import { hasRolePermission } from "../../../platform/permissions";
import { useBillingAccessStatus } from "../../billing/hooks/useBilling";
import { isTenantSubdomain } from "../../../utils/domain";

export type AllowedRole = "user" | "admin" | "owner";

interface ProtectedRouteProps {
  children: ReactNode;
  allowedRoles?: Array<AllowedRole>;
  requiredPermission?: string;
  loadingFallback?: ReactNode;
}

const BILLING_ALLOWED_PATHS = ["/admin/szamlak", "/admin/szamlak/kiegyenlites"];

function isBillingAllowedPath(pathname: string): boolean {
  return BILLING_ALLOWED_PATHS.some((path) => pathname === path || pathname.startsWith(`${path}/`));
}

export default function ProtectedRoute({ children, allowedRoles, requiredPermission, loadingFallback }: ProtectedRouteProps) {
  const { token, user, loadingUser } = useAuthStore();
  const { t } = useTranslation();
  const location = useLocation();
  const onTenantHost = isTenantSubdomain();
  const { data: accessStatus, isLoading: accessLoading } = useBillingAccessStatus({
    enabled: Boolean(token && user && onTenantHost),
    staleTime: 15_000,
  });

  if (loadingUser && loadingFallback) return <>{loadingFallback}</>;
  if (!token || !user) {
    const safePath = getSafeLoginRedirect(location.pathname || "/chat");
    const redirect = safePath !== "/chat" ? `?redirect=${encodeURIComponent(safePath)}` : "";
    return <Navigate to={`/login${redirect}`} replace />;
  }
  if (allowedRoles != null && allowedRoles.length > 0 && !allowedRoles.includes(user.role)) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center gap-4 p-6 text-black">
        <p className="text-lg">{t("common.accessDenied")}</p>
        <Link to="/chat" className="text-blue-600 underline">
          {t("nav.chat")}
        </Link>
      </div>
    );
  }
  if (requiredPermission && !hasRolePermission(user.role, requiredPermission)) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center gap-4 p-6 text-black">
        <p className="text-lg">{t("common.accessDenied")}</p>
        <Link to="/chat" className="text-blue-600 underline">
          {t("nav.chat")}
        </Link>
      </div>
    );
  }

  if (onTenantHost && accessLoading && loadingFallback) return <>{loadingFallback}</>;

  const billingLock = Boolean(accessStatus?.billing_lock);
  if (billingLock && !isBillingAllowedPath(location.pathname)) {
    const redirectPath = accessStatus?.redirect_path || "/admin/szamlak/kiegyenlites";
    if (user.role === "owner" || hasRolePermission(user.role, "billing.manage")) {
      return <Navigate to={redirectPath} replace />;
    }
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center gap-4 p-6 text-[var(--color-foreground)]">
        <p className="text-lg text-center max-w-md">
          A szolgáltatás tartozás miatt korlátozott. A kiegyenlítést a tulajdonos tudja elvégezni a számlázás oldalon.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}

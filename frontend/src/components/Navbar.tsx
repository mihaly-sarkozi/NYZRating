import { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "../i18n";
import { useAuthStore } from "../store/authStore";
import { hasUserPermission } from "../platform/permissions";
import { getModuleMenuDefinitions, getAuthenticatedFallbackPath } from "../platform/moduleRegistry";
import { useBillingAccessStatus } from "../features/billing/hooks/useBilling";
import { isTenantSubdomain } from "../utils/domain";

type NavbarProps = {
  topOffsetClassName?: string;
};

export default function Navbar({
  topOffsetClassName = "top-0",
}: NavbarProps) {
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const hamburgerButtonRef = useRef<HTMLDivElement | null>(null);
  const hamburgerMenuRef = useRef<HTMLDivElement | null>(null);
  const { data: accessStatus } = useBillingAccessStatus({
    enabled: Boolean(user) && isTenantSubdomain(),
    staleTime: 15_000,
  });
  const billingLock = Boolean(accessStatus?.billing_lock);

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node | null;
      const clickedHamburgerButton = Boolean(hamburgerButtonRef.current && target && hamburgerButtonRef.current.contains(target));
      const clickedHamburgerMenu = Boolean(hamburgerMenuRef.current && target && hamburgerMenuRef.current.contains(target));
      if (menuOpen && !clickedHamburgerButton && !clickedHamburgerMenu) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [menuOpen]);

  const handleLogout = () => {
    setMenuOpen(false);
    logout();
    navigate("/login", { replace: true });
  };

  const go = (path: string) => {
    setMenuOpen(false);
    navigate(path);
  };

  const visibleMenuItems = getModuleMenuDefinitions()
    .filter((item) => (item.requiresAuth ? Boolean(user) : true))
    .filter((item) => (item.requiredPermission ? hasUserPermission(user, item.requiredPermission) : true))
    .filter((item) => {
      if (!item.allowedRoles?.length) return true;
      return Boolean(user && item.allowedRoles.includes(user.role));
    })
    .filter((item) => {
      if (!billingLock) return true;
      return item.path === "/admin/szamlak" || item.path.startsWith("/admin/szamlak/");
    })
    .sort((a, b) => (a.order ?? 999) - (b.order ?? 999))
    .map((item) => ({
      key: item.key,
      label: t(item.labelKey),
      path: item.path,
      order: item.order ?? 999,
    }));

  const leftMenuSections = [
    visibleMenuItems.filter((item) => item.order < 40),
    visibleMenuItems.filter((item) => item.order >= 40 && item.order < 50),
    visibleMenuItems.filter((item) => item.order >= 50),
  ].filter((section) => section.length > 0);

  const showHamburger = !user || visibleMenuItems.length > 0;

  useEffect(() => {
    if (!showHamburger) setMenuOpen(false);
  }, [showHamburger]);

  return (
    <nav className={`w-full bg-[var(--color-background)] text-[var(--color-foreground)] border-b border-[var(--color-border)] fixed ${topOffsetClassName} left-0 z-50`}>
      <div className="p-2 flex items-center justify-between gap-2">
        <div ref={hamburgerButtonRef} className="flex items-center shrink-0">
          {showHamburger ? (
            <button
              type="button"
              onClick={() => setMenuOpen((o) => !o)}
              className="p-2 rounded hover:bg-gray-200 dark:hover:bg-gray-700 shrink-0"
              aria-expanded={menuOpen}
              aria-label={menuOpen ? "Menü bezárása" : "Menü"}
            >
              {menuOpen ? (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              )}
            </button>
          ) : null}
        </div>
        <button
          type="button"
          onClick={() => {
            setMenuOpen(false);
            if (user) {
              const fallback = getAuthenticatedFallbackPath();
              if (location.pathname !== fallback) navigate(fallback);
            } else {
              navigate("/");
            }
          }}
          className="mr-[10px] font-semibold text-[var(--color-foreground)] truncate text-right"
        >
          NYZ Rating
        </button>
      </div>

      {/* Lenyíló menü – keskeny, balra igazított sáv */}
      {showHamburger && menuOpen && (
        <div ref={hamburgerMenuRef} className="absolute left-2 top-full mt-2 w-56 rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] shadow-lg py-2 z-[60]">
          {leftMenuSections.map((section, sectionIdx) => (
            <div key={`menu-section-${sectionIdx}`} className="flex flex-col gap-1 px-2">
              {section.map((item) => (
                <button
                  key={item.key}
                  onClick={() => go(item.path)}
                  className="w-full rounded-md px-2 py-2 text-left text-sm text-[var(--color-muted)] hover:bg-[var(--color-border)]/20 hover:text-[var(--color-foreground)]"
                >
                  {item.label}
                </button>
              ))}
              {sectionIdx < leftMenuSections.length - 1 ? (
                <div className="my-2 border-t border-gray-200 dark:border-gray-600" />
              ) : null}
            </div>
          ))}
          {user && (
            <button
              onClick={handleLogout}
              className="mx-2 mt-2 w-[calc(100%-1rem)] border-t border-gray-200 px-2 pt-3 text-left text-sm text-red-600 hover:text-red-700 dark:border-gray-600 dark:text-red-400 dark:hover:text-red-300"
            >
              {t("common.logout")}
            </button>
          )}
        </div>
      )}
    </nav>
  );
}

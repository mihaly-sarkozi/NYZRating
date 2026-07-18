// backend/apps/settings/web/module.tsx
// Feladat: Settings frontend modul – számlázási beállítások + ideiglenes tenant reset oldal.
// Sárközi Mihály - 2026.05.24

import type { FrontendModuleDefinition } from "@frontend/platform/moduleTypes";

export function getModule(): FrontendModuleDefinition {
  return {
    key: "settings",
    routes: () => [
      {
        key: "settings.page",
        path: "/admin/settings",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "settings.read",
        loader: () => import("@frontend/features/settings/pages/SettingsPage"),
      },
      {
        key: "settings.tenantReset",
        path: "/admin/settings/reset",
        layout: "main",
        requiresAuth: true,
        requiredPermission: "settings.write",
        allowedRoles: ["owner"],
        loader: () => import("@frontend/features/settings/pages/TenantResetPage"),
      },
    ],
    menuItems: () => [
      {
        key: "settings.billing",
        path: "/admin/settings",
        labelKey: "nav.settings",
        requiresAuth: true,
        requiredPermission: "settings.read",
        order: 60,
      },
      {
        key: "settings.tenantReset",
        path: "/admin/settings/reset",
        labelKey: "nav.tenantReset",
        requiresAuth: true,
        requiredPermission: "settings.write",
        allowedRoles: ["owner"],
        order: 61,
      },
    ],
  };
}

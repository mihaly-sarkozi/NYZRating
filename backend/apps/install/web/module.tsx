import type { FrontendModuleDefinition } from "@frontend/platform/moduleTypes";

export function getModule(): FrontendModuleDefinition {
  return {
    key: "install",
    routes: () => [
      {
        key: "install.registration",
        path: "/registration",
        layout: "public",
        loader: () => import("@frontend/features/install/pages/InstallPage"),
      },
      {
        key: "install.page",
        path: "/install",
        layout: "public",
        loader: () => import("@frontend/features/install/pages/InstallPage"),
      },
      {
        key: "install.login",
        path: "/install-login",
        layout: "public",
        loader: () => import("@frontend/features/install/pages/InstallLoginPage"),
      },
      {
        key: "install.expired",
        path: "/install-expired",
        layout: "public",
        loader: () => import("@frontend/features/install/pages/InstallExpiredPage"),
      },
      {
        key: "install.email-sent",
        path: "/install-email-sent",
        layout: "public",
        loader: () => import("@frontend/features/install/pages/InstallEmailSentPage"),
      },
      {
        key: "install.confirm-signup",
        path: "/confirm-signup",
        layout: "public",
        loader: () => import("@frontend/features/install/pages/ConfirmSignupPage"),
      },
      // Legacy /demo* → /install* redirects (a /demo telepítőfolyamat megmarad)
      {
        key: "install.legacy.page",
        path: "/demo",
        layout: "public",
        loader: () => import("@frontend/features/install/pages/LegacyDemoRedirect"),
      },
      {
        key: "install.legacy.login",
        path: "/demo-login",
        layout: "public",
        loader: () => import("@frontend/features/install/pages/LegacyDemoRedirect"),
      },
      {
        key: "install.legacy.expired",
        path: "/demo-expired",
        layout: "public",
        loader: () => import("@frontend/features/install/pages/LegacyDemoRedirect"),
      },
      {
        key: "install.legacy.email-sent",
        path: "/demo-email-sent",
        layout: "public",
        loader: () => import("@frontend/features/install/pages/LegacyDemoRedirect"),
      },
    ],
    menuItems: () => [],
  };
}

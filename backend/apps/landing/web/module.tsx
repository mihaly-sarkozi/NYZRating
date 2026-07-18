import type { FrontendModuleDefinition } from "@frontend/platform/moduleTypes";

export function getModule(): FrontendModuleDefinition {
  return {
    key: "landing",
    routes: () => [
      {
        key: "landing.root",
        path: "/",
        layout: "public",
        loader: () => import("@frontend/features/landing/pages/LandingEntryRoute"),
      },
    ],
    menuItems: () => [],
  };
}

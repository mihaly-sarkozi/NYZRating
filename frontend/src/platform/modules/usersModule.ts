import type { FrontendModuleDefinition } from "../moduleTypes";

export function getModule(): FrontendModuleDefinition {
  return {
    key: "users",
    // Ebben a verzióban nincs felhasználó-/jogosultságkezelés UI (egy owner az installnál).
    routes: () => [],
    menuItems: () => [],
  };
}

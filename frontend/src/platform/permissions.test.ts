import { describe, expect, it } from "vitest";

import { hasRolePermission, hasUserPermission } from "./permissions";
import type { FrontendUser } from "./moduleTypes";

describe("frontend permissions", () => {
  it("allows owner wildcard permissions", () => {
    expect(hasRolePermission("owner", "settings.read")).toBe(true);
    expect(hasRolePermission("owner", "unknown.permission")).toBe(true);
  });

  it("allows admin permissions intended for admins", () => {
    expect(hasRolePermission("admin", "users.write")).toBe(true);
    expect(hasRolePermission("admin", "settings.read")).toBe(true);
    expect(hasRolePermission("admin", "settings.write")).toBe(true);
  });

  it("denies admin/settings style permissions for regular users", () => {
    expect(hasRolePermission("user", "users.write")).toBe(false);
    expect(hasRolePermission("user", "settings.read")).toBe(false);
  });

  it("denies unknown roles", () => {
    expect(hasRolePermission("support" as "user", "settings.read")).toBe(false);
  });

  it("checks user permissions through the user adapter", () => {
    const user: FrontendUser = { id: 1, email: "u@example.test", role: "admin" };
    expect(hasUserPermission(user, "users.read")).toBe(true);
    expect(hasUserPermission(null, "users.read")).toBe(false);
  });
});

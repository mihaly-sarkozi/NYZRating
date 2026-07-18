import { useMemo } from "react";
import { Link } from "react-router-dom";

import { getTenantBaseDomain } from "../../../utils/domain";

function installUrl(): string {
  const scheme = window.location.protocol || "http:";
  const host = getTenantBaseDomain();
  const port = window.location.port ? `:${window.location.port}` : "";
  return `${scheme}//${host}${port}/install`;
}

export default function InstallExpiredPage() {
  const continueUrl = useMemo(() => installUrl(), []);

  return (
    <div className="min-h-screen bg-[var(--color-background)] text-[var(--color-foreground)] flex flex-col">
      <header className="border-b border-[var(--color-border)] px-4 py-4">
        <Link to="/install" className="text-sm text-[var(--color-muted-foreground)] hover:underline">
          ← Vissza a telepítő oldalra
        </Link>
      </header>
      <main className="flex-1 flex items-center justify-center px-4">
        <div className="max-w-lg w-full text-center space-y-4">
          <h1 className="text-3xl font-bold">A próbaverzió véget ért</h1>
          <p className="text-[var(--color-muted-foreground)]">
            Ha szeretnéd folytatni, kattints a gombra.
          </p>
          <a
            href={continueUrl}
            className="inline-flex items-center justify-center rounded bg-[var(--color-primary)] px-6 py-3 font-medium text-white"
          >
            Szeretném folytatni
          </a>
        </div>
      </main>
    </div>
  );
}

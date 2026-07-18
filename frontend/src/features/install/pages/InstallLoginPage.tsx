import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { consumeInstallLogin, resolveInstallLogin } from "../api/installApi";
import { fetchCsrfToken } from "../../../api/axiosClient";
import { isDemoInitialPasswordMode, useAuthStore } from "../../../store/authStore";
import { getTenantBaseDomain, isTenantSubdomain } from "../../../utils/domain";

function installBaseUrl(): string {
  const scheme = window.location.protocol || "http:";
  const host = getTenantBaseDomain();
  const port = window.location.port ? `:${window.location.port}` : "";
  return `${scheme}//${host}${port}`;
}

export default function InstallLoginPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { setToken, loadUser } = useAuthStore();
  const [message, setMessage] = useState("A telepítő link ellenőrzése folyamatban…");
  const [error, setError] = useState("");
  const token = useMemo(() => searchParams.get("token") || "", [searchParams]);

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      if (!token) {
        setError("Hiányzik a telepítő token.");
        setMessage("");
        return;
      }

      try {
        if (!isTenantSubdomain()) {
          const data = await resolveInstallLogin(token);
          if (!cancelled) window.location.replace(data.redirect_to);
          return;
        }

        setMessage("Beléptetés folyamatban…");
        await fetchCsrfToken();
        const data = await consumeInstallLogin(token);
        if (cancelled) return;
        setToken(data.access_token);
        await loadUser();
        const currentUser = useAuthStore.getState().user;
        navigate(isDemoInitialPasswordMode(currentUser) ? "/change-password" : "/chat", { replace: true });
      } catch (err: unknown) {
        if (cancelled) return;
        const status =
          err && typeof err === "object" && "response" in err
            ? (err as { response?: { status?: number } }).response?.status
            : undefined;

        if (status === 410) {
          window.location.replace(`${installBaseUrl()}/install-expired`);
          return;
        }

        setMessage("");
        setError("A telepítő link nem használható. Kérj új linket a telepítő oldalról.");
      }
    };

    void run();
    return () => {
      cancelled = true;
    };
  }, [loadUser, navigate, setToken, token]);

  return (
    <div className="min-h-screen bg-[var(--color-background)] text-[var(--color-foreground)] flex flex-col">
      <header className="border-b border-[var(--color-border)] px-4 py-4">
        <Link to="/install" className="text-sm text-[var(--color-muted-foreground)] hover:underline">
          ← Vissza a telepítő oldalra
        </Link>
      </header>
      <main className="flex-1 flex items-center justify-center px-4">
        <div className="max-w-md w-full text-center">
          {message && <p className="text-lg font-medium">{message}</p>}
          {error && <p className="text-sm text-red-600">{error}</p>}
        </div>
      </main>
    </div>
  );
}

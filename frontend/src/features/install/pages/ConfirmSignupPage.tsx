import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { confirmInstallSignup, type ConfirmSignupResponse } from "../api/installApi";

type Status = "loading" | "ok" | "invalid" | "expired" | "error";

/**
 * Strict Mode kétszer mountolja az effectet: az első cleanup cancelled=true,
 * a második pedig ne indítson új requestet, de várja meg ugyanazt a promise-t.
 */
const confirmPromises = new Map<string, Promise<ConfirmSignupResponse>>();

function confirmOnce(token: string): Promise<ConfirmSignupResponse> {
  const existing = confirmPromises.get(token);
  if (existing) return existing;
  const promise = confirmInstallSignup(token).catch((err) => {
    confirmPromises.delete(token);
    throw err;
  });
  confirmPromises.set(token, promise);
  return promise;
}

export default function ConfirmSignupPage() {
  const [searchParams] = useSearchParams();
  const token = (searchParams.get("token") || "").trim();
  const [status, setStatus] = useState<Status>("loading");
  const [message, setMessage] = useState("Email megerősítése…");

  useEffect(() => {
    if (!token) {
      setStatus("invalid");
      setMessage("Hiányzó vagy érvénytelen megerősítő link.");
      return;
    }

    let cancelled = false;
    confirmOnce(token)
      .then((res) => {
        if (cancelled) return;
        const url = (res.set_password_url || "").trim();
        if (url) {
          window.location.assign(url);
          return;
        }
        setStatus("ok");
        setMessage(res.message || "Email megerősítve. Ellenőrizd a postafiókod a jelszóbeállító linkért.");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const ax = err as { response?: { status?: number; data?: { detail?: unknown } } };
        const detail = ax.response?.data?.detail;
        const msg =
          typeof detail === "object" && detail && "message" in detail
            ? String((detail as { message?: string }).message)
            : typeof detail === "string"
              ? detail
              : "A megerősítés nem sikerült.";
        setMessage(msg);
        setStatus(ax.response?.status === 410 ? "expired" : "invalid");
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <div className="min-h-screen bg-[var(--color-background)] text-[var(--color-foreground)] flex flex-col">
      <header className="border-b border-[var(--color-border)] px-4 py-4">
        <Link to="/install" className="text-sm text-[var(--color-muted-foreground)] hover:underline">
          ← Vissza a telepítő oldalra
        </Link>
      </header>
      <main className="flex-1 flex items-center justify-center px-4">
        <div className="max-w-lg w-full rounded border border-[var(--color-border)] bg-[var(--color-card)] p-6 md:p-8">
          <h1 className="text-2xl font-bold mb-4">
            {status === "loading" ? "Megerősítés folyamatban" : status === "ok" ? "Email megerősítve" : "A link nem érvényes"}
          </h1>
          <p className="text-[var(--color-muted-foreground)] mb-3">{message}</p>
          {(status === "invalid" || status === "expired") && (
            <p className="text-sm text-[var(--color-muted-foreground)]">
              Indítsd újra a regisztrációt az{" "}
              <Link to="/install" className="underline">
                install
              </Link>{" "}
              oldalon.
            </p>
          )}
        </div>
      </main>
    </div>
  );
}

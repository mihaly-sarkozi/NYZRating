import { useCallback, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { installSignup, type InstallSignupResponse } from "../api/installApi";
import TurnstileWidget, { getTurnstileSiteKey, resetTurnstile } from "../components/TurnstileWidget";
import { useTranslation } from "../../../i18n";

export const INSTALL_SESSION_STORAGE_KEY = "nyzrating_install_session_id";

function generateSessionId(): string {
  const cryptoApi = typeof window !== "undefined" ? window.crypto : undefined;
  if (cryptoApi && typeof cryptoApi.randomUUID === "function") {
    return cryptoApi.randomUUID();
  }

  const randomPart = Math.random().toString(36).slice(2);
  return `install-${Date.now()}-${randomPart}`;
}

function getOrCreateInstallSessionId(): string {
  const existing = sessionStorage.getItem(INSTALL_SESSION_STORAGE_KEY)?.trim();
  if (existing) {
    return existing;
  }

  const generated = generateSessionId();
  sessionStorage.setItem(INSTALL_SESSION_STORAGE_KEY, generated);
  return generated;
}

export default function InstallPage() {
  const { locale } = useTranslation();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [existingInstall, setExistingInstall] = useState<{ email: string } | null>(null);
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const turnstileRequired = Boolean(getTurnstileSiteKey());
  const onCaptchaTokenChange = useCallback((token: string | null) => {
    setCaptchaToken(token);
  }, []);

  const canSubmit =
    Boolean(email.trim() && companyName.trim()) && (!turnstileRequired || Boolean(captchaToken));

  const submitInstall = async (resendExistingAccess: boolean): Promise<InstallSignupResponse> => {
    const company = companyName.trim();
    if (turnstileRequired && !captchaToken) {
      throw new Error("Captcha token missing");
    }
    // Ugyanaz a session a retry/resend alatt → slug foglalás idempotens marad.
    const sessionId = getOrCreateInstallSessionId();
    const res = await installSignup({
      email: email.trim(),
      name: company,
      company_name: company,
      locale,
      resend_existing_access: resendExistingAccess,
      kb_name: company,
      plan_code: "free",
      billing_period: "monthly",
      demo_session_id: sessionId,
      captcha_token: captchaToken || undefined,
    });
    sessionStorage.removeItem(INSTALL_SESSION_STORAGE_KEY);
    resetTurnstile();
    setCaptchaToken(null);
    const params = new URLSearchParams();
    params.set("email", email.trim());
    if (resendExistingAccess) params.set("resent", "1");
    params.set("mode", res.awaiting_email_verification ? "confirm" : "password");
    navigate(`/install-email-sent?${params.toString()}`, { replace: true });
    return res;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting || !canSubmit) return;
    setSubmitError("");
    setExistingInstall(null);
    setSubmitting(true);
    try {
      await submitInstall(false);
    } catch (err: unknown) {
      const response =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { status?: number; data?: { detail?: string | { reason?: string; message?: string } } } })
              .response
          : null;
      const responseData = response?.data ?? null;
      const detail = responseData?.detail;
      const reason = typeof detail === "object" && detail ? detail.reason : undefined;
      const message = typeof detail === "object" && detail ? detail.message : detail;
      const normalizedMessage = (typeof message === "string" ? message : "").toLowerCase();
      const isExistingInstallLike =
        reason === "demo_exists" ||
        response?.status === 409 ||
        normalizedMessage.includes("already") ||
        normalizedMessage.includes("már") ||
        normalizedMessage.includes("használatban");
      resetTurnstile();
      setCaptchaToken(null);
      if (isExistingInstallLike) {
        // Turnstile token egyszer használható → ne auto-resendeljünk; új captcha + modal.
        setExistingInstall({ email: email.trim() });
        setSubmitError("");
      } else {
        setSubmitError(typeof message === "string" ? message : "Hiba történt. Próbáld újra.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleResendAccess = async () => {
    if (submitting || !canSubmit) return;
    setSubmitError("");
    setSubmitting(true);
    try {
      await submitInstall(true);
      setExistingInstall(null);
    } catch (err: unknown) {
      resetTurnstile();
      setCaptchaToken(null);
      const responseData =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string | { message?: string } } } }).response?.data
          : null;
      const detail = responseData?.detail;
      const message = typeof detail === "object" && detail ? detail.message : detail;
      setSubmitError(typeof message === "string" ? message : "Hiba történt. Próbáld újra.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--color-background)] text-[var(--color-foreground)] flex flex-col">
      <header className="border-b border-[var(--color-border)] px-4 py-4 flex justify-between items-center">
        <Link to="/" className="text-sm text-[var(--color-muted-foreground)] hover:underline">
          ← Vissza
        </Link>
        <span className="font-semibold">1 perc a telepítés</span>
      </header>

      <main className="flex-1 px-4 py-8 max-w-lg mx-auto w-full">
        <h1 className="text-3xl font-bold mb-3">Szerezzen több Google-értékelést automatikusan</h1>
        <p className="text-base text-[var(--color-muted-foreground)] mb-2">
          Állítsa be vállalkozását, és küldjön személyre szabott SMS-t ügyfeleinek a Google értékelési oldalára.
        </p>
        <p className="text-base text-[var(--color-muted-foreground)] mb-8">
          Az ingyenes kipróbálással megmutatjuk, hogyan gyűjt több őszinte értékelést a NYZ Rating.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Cégnév</label>
            <input
              type="text"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              className="w-full rounded border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-3"
              required
              placeholder="Példa Kft."
              autoComplete="organization"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Email címed</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-3"
              required
              placeholder="email@pelda.hu"
            />
          </div>

          {turnstileRequired ? (
            <TurnstileWidget onTokenChange={onCaptchaTokenChange} className="min-h-[65px]" />
          ) : null}

          {submitError && <p className="text-sm text-red-600">{submitError}</p>}
          <div className="pt-2">
            <button
              type="submit"
              disabled={submitting || !canSubmit}
              className="w-full px-6 py-3 rounded bg-[var(--color-primary)] text-white font-medium disabled:opacity-50"
            >
              {submitting ? "Telepítés…" : "Kipróbálom ingyen"}
            </button>
          </div>

          <p className="text-sm text-[var(--color-muted-foreground)]">
            Nincs kötelezettség, nincs szükség bankkártyára.
          </p>
          <p className="text-sm text-[var(--color-muted-foreground)]">
            Az adataidat bizalmasan kezeljük.{" "}
            <a
              href={`/api/installer/privacy-policy.pdf?lang=${encodeURIComponent(locale)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="underline"
            >
              adatkezelési tájékoztató
            </a>
          </p>
        </form>
      </main>

      {existingInstall && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
          role="dialog"
          aria-modal="true"
          aria-labelledby="install-exists-title"
          onClick={() => {
            if (!submitting) setExistingInstall(null);
          }}
        >
          <div
            className="relative w-full max-w-md rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] p-6 shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="install-exists-title" className="text-lg font-semibold text-[var(--color-foreground)] mb-3">
              Figyelem
            </h2>
            <p className="text-sm text-[var(--color-foreground)] mb-2">
              Ezzel az email címmel már hoztál létre telepítést.
            </p>
            <p className="text-sm text-[var(--color-muted-foreground)] mb-6">
              Oldd meg újra a captchát az űrlapon, majd kattints ide, ha új linket szeretnél.
            </p>
            <p className="text-xs text-[var(--color-muted-foreground)] mb-4">
              A megerősítő / jelszóbeállító linket emailben küldjük.
            </p>
            <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={() => setExistingInstall(null)}
                disabled={submitting}
                className="inline-flex items-center justify-center rounded border border-[var(--color-border)] px-4 py-2 text-[var(--color-foreground)] disabled:opacity-50 order-2 sm:order-1"
              >
                Vissza
              </button>
              <button
                type="button"
                onClick={handleResendAccess}
                disabled={submitting}
                className="inline-flex items-center justify-center rounded bg-[var(--color-primary)] px-4 py-2 font-medium text-white disabled:opacity-50 order-1 sm:order-2"
              >
                {submitting ? "Küldés…" : "Új elérést szeretnék"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

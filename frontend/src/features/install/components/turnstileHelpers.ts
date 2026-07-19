export function getTurnstileSiteKey(): string {
  return String(import.meta.env.VITE_TURNSTILE_SITE_KEY || "").trim();
}

export function resetTurnstile(): void {
  if (typeof window === "undefined" || !window.turnstile) return;
  try {
    window.turnstile.reset();
  } catch {
    /* ignore */
  }
}

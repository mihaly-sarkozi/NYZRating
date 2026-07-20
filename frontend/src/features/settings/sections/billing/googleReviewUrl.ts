/** Google g.page review link helpers (registration + billing settings). */

const GOOGLE_REVIEW_URL_RE = /^https:\/\/g\.page\/r\/[A-Za-z0-9_\-]+\/review\/?$/i;

export function normalizeGoogleReviewUrl(value: string | null | undefined): string {
  const normalized = (value || "").trim();
  if (!normalized) return "";
  return normalized.replace(/\/+$/, "");
}

export function isValidGoogleReviewUrl(value: string | null | undefined): boolean {
  const normalized = normalizeGoogleReviewUrl(value);
  if (!normalized) return false;
  return GOOGLE_REVIEW_URL_RE.test(`${normalized}/`);
}

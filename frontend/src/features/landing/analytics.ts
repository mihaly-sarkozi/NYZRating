/** Landing CTA mérési események (dataLayer + custom event). */

export type LandingAnalyticsEvent =
  | "landing_trial_clicked"
  | "landing_pricing_clicked"
  | "landing_demo_started"
  | "landing_login_clicked"
  | "landing_faq_opened";

type LandingEventPayload = Record<string, string | number | boolean | undefined>;

export function trackLandingEvent(event: LandingAnalyticsEvent, payload: LandingEventPayload = {}): void {
  if (typeof window === "undefined") return;

  const detail = { event, ...payload, ts: Date.now() };

  try {
    window.dispatchEvent(new CustomEvent("nyz-analytics", { detail }));
  } catch {
    /* ignore */
  }

  const w = window as Window & { dataLayer?: Array<Record<string, unknown>> };
  w.dataLayer = w.dataLayer ?? [];
  w.dataLayer.push(detail);
}

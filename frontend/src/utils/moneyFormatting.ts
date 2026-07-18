/** Locale tag számformázáshoz. */
export function localeTagForNumbers(locale: string): string {
  if (locale === "es") return "es-ES";
  if (locale === "en") return "en-GB";
  return "hu-HU";
}

/**
 * Egész Ft összeg megjelenítése.
 * Magyar: ezres elválasztó pont (8.000), tizedes nélkül.
 * En/es: locale szerinti ezres elválasztó, tizedes nélkül.
 */
export function formatForintAmount(amount: number, locale = "hu"): string {
  const value = Math.round(Number(amount) || 0);
  if (locale === "hu" || localeTagForNumbers(locale) === "hu-HU") {
    const sign = value < 0 ? "-" : "";
    const digits = String(Math.abs(value));
    return `${sign}${digits.replace(/\B(?=(\d{3})+(?!\d))/g, ".")}`;
  }
  return value.toLocaleString(localeTagForNumbers(locale), { maximumFractionDigits: 0 });
}

/** Cents (fillér) → egész Ft string. */
export function formatForintFromCents(cents: number, locale = "hu"): string {
  return formatForintAmount(Number(cents) / 100, locale);
}

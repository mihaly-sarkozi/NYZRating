// frontend/src/features/settings/countries/billingCountries.ts
// Feladat: A settings számlázási cím/ország mezőinek helper- és adatkészlete.
// Ez a settings modul saját, önálló koncepciója (nem a billing/subscription app-hoz
// tartozik), ezért itt él, nem egy külön "billing" feature alatt.
// A country-kód lista és a régió-policy a backend
// apps/settings/domain/billing_countries.py forrásával van szinkronban tartva.

export type BillingCustomerType = "company" | "private";

export const BILLING_COUNTRY_OTHER = "OTHER";

const EU_COUNTRY_CODES = [
  "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR",
  "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO",
  "SE", "SI", "SK",
] as const;

const EUROPEAN_EXTRA_COUNTRY_CODES = [
  "AD", "AL", "BA", "CH", "GB", "IS", "LI", "MC", "MD", "ME", "MK", "NO",
  "RS", "SM", "TR", "UA", "VA", "XK",
] as const;

const EUROPEAN_COUNTRY_CODES = [...EU_COUNTRY_CODES, ...EUROPEAN_EXTRA_COUNTRY_CODES];

const REGION_REQUIRED_COUNTRY_CODES = ["CH", "ES", "GB", "IT"] as const;

const VAT_PREFIX_BY_COUNTRY_CODE: Record<string, string> = { GR: "EL" };

export const BILLING_REGIONS_BY_COUNTRY: Record<string, string[]> = {
  CH: [
    "Aargau", "Appenzell Ausserrhoden", "Appenzell Innerrhoden", "Basel-Landschaft",
    "Basel-Stadt", "Bern", "Fribourg", "Genève", "Glarus", "Graubünden", "Jura",
    "Luzern", "Neuchâtel", "Nidwalden", "Obwalden", "Schaffhausen", "Schwyz",
    "Solothurn", "St. Gallen", "Thurgau", "Ticino", "Uri", "Valais", "Vaud",
    "Zug", "Zürich",
  ],
  ES: [
    "Andalucía", "Aragón", "Asturias", "Baleares", "Canarias", "Cantabria",
    "Castilla-La Mancha", "Castilla y León", "Cataluña", "Ceuta", "Extremadura",
    "Galicia", "La Rioja", "Madrid", "Melilla", "Murcia", "Navarra",
    "País Vasco", "Comunidad Valenciana",
  ],
  GB: ["England", "Scotland", "Wales", "Northern Ireland"],
  IT: [
    "Abruzzo", "Basilicata", "Calabria", "Campania", "Emilia-Romagna",
    "Friuli-Venezia Giulia", "Lazio", "Liguria", "Lombardia", "Marche",
    "Molise", "Piemonte", "Puglia", "Sardegna", "Sicilia", "Toscana",
    "Trentino-Alto Adige", "Umbria", "Valle d'Aosta", "Veneto",
  ],
};

function normalizeCountryCode(value: string | null | undefined): string {
  return String(value ?? "").trim().toUpperCase().replace(/\s+/g, "_");
}

export function isEuropeanBillingCountry(countryCode: string | null | undefined): boolean {
  return EUROPEAN_COUNTRY_CODES.includes(normalizeCountryCode(countryCode));
}

export function isEuBillingCountry(countryCode: string | null | undefined): boolean {
  return (EU_COUNTRY_CODES as readonly string[]).includes(normalizeCountryCode(countryCode));
}

export function isRegionRequired(countryCode: string | null | undefined): boolean {
  return (REGION_REQUIRED_COUNTRY_CODES as readonly string[]).includes(normalizeCountryCode(countryCode));
}

export function vatPrefixForCountry(countryCode: string | null | undefined): string {
  const normalized = normalizeCountryCode(countryCode);
  return VAT_PREFIX_BY_COUNTRY_CODE[normalized] ?? normalized;
}

export function getEuVatPlaceholder(countryCode: string | null | undefined): string {
  const prefix = vatPrefixForCountry(countryCode);
  return prefix ? `${prefix}123456789` : "EU123456789";
}

export function normalizeEuVatId(value: string | null | undefined): string {
  return String(value ?? "")
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, "");
}

export function isValidEuVatId(value: string | null | undefined, countryCode: string | null | undefined): boolean {
  const normalized = normalizeEuVatId(value);
  if (!normalized) return false;
  const prefix = vatPrefixForCountry(countryCode);
  if (prefix && !normalized.startsWith(prefix)) return false;
  const digits = normalized.slice(prefix.length);
  return digits.length >= 2 && digits.length <= 12 && /^[A-Z0-9]+$/.test(digits);
}

export function normalizePostalCode(value: string | null | undefined): string {
  return String(value ?? "").trim().toUpperCase();
}

let countryDisplayNames: Intl.DisplayNames | null = null;
function getCountryDisplayNames(): Intl.DisplayNames | null {
  if (typeof Intl === "undefined" || typeof Intl.DisplayNames === "undefined") return null;
  if (!countryDisplayNames) {
    countryDisplayNames = new Intl.DisplayNames(["en"], { type: "region" });
  }
  return countryDisplayNames;
}

export function getBillingCountryLabel(countryCode: string): string {
  if (countryCode === BILLING_COUNTRY_OTHER) return "Other";
  const displayNames = getCountryDisplayNames();
  return displayNames?.of(countryCode) ?? countryCode;
}

export function getBillingCountryOptions(): Array<{ value: string; label: string }> {
  const codes = [...EUROPEAN_COUNTRY_CODES].sort((a, b) => getBillingCountryLabel(a).localeCompare(getBillingCountryLabel(b)));
  return [
    ...codes.map((code) => ({ value: code, label: getBillingCountryLabel(code) })),
    { value: BILLING_COUNTRY_OTHER, label: getBillingCountryLabel(BILLING_COUNTRY_OTHER) },
  ];
}

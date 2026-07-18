// frontend/src/features/traffic/validation/huMobile.ts
// Feladat: Magyar mobilszám kliensoldali normalizálás és validáció.
// Sárközi Mihály - 2026.07.18

const MOBILE_PREFIXES = new Set(["20", "30", "31", "50", "70"]);

export function normalizeHuMobile(value: string): string {
  let raw = value.replace(/[\s./()-]/g, "");
  if (!raw) return "";
  if (raw.startsWith("00")) raw = `+${raw.slice(2)}`;
  let digits: string;
  if (raw.startsWith("+")) {
    digits = raw.slice(1).replace(/\D/g, "");
  } else {
    digits = raw.replace(/\D/g, "");
    if (digits.startsWith("06")) digits = `36${digits.slice(2)}`;
    else if (digits.startsWith("6") && digits.length === 10) digits = `3${digits}`;
    else if (digits.length === 9 && MOBILE_PREFIXES.has(digits.slice(0, 2))) digits = `36${digits}`;
  }
  if (!digits.startsWith("36")) return "";
  return `+${digits}`;
}

export function isValidHuMobile(value: string): boolean {
  const normalized = normalizeHuMobile(value);
  if (!/^\+36\d{9}$/.test(normalized)) return false;
  return MOBILE_PREFIXES.has(normalized.slice(3, 5));
}

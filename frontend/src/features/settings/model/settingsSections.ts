// frontend/src/features/settings/model/settingsSections.ts
// Feladat: A settings szekciók kulcsainak és tab-listájának központi modellje.
// Sárközi Mihály - 2026.05.29

export type SettingsSectionKey = "security" | "preferences" | "billing" | "domains" | "reset";

export type SettingsSectionTab = {
  key: SettingsSectionKey;
  label: string;
};

/** Egyelőre csak a számlázás látszik a beállítások oldalon (nincs almenü). */
export function buildSettingsSections(
  t: (key: string) => string,
  includeBusinessSections: boolean,
  _includeResetSection: boolean
): SettingsSectionTab[] {
  if (!includeBusinessSections) return [];
  return [{ key: "billing", label: t("settings.sectionBilling") }];
}

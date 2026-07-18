// frontend/src/features/settings/shell/SettingsShell.tsx
// Feladat: A settings oldal shell – egyelőre csak számlázási beállítások (nincs almenü).
// Sárközi Mihály - 2026.05.29

import { useTranslation } from "../../../i18n";
import type { User } from "../../../store/authStore";
import { canManageBillingAndDomains } from "../model/settingsPermissions";
import BillingSettingsContainer from "../sections/billing/BillingSettingsContainer";
import SettingsHeader from "./SettingsHeader";

type SettingsShellProps = {
  user: User;
};

export default function SettingsShell({ user }: SettingsShellProps) {
  const { t } = useTranslation();
  const showBilling = canManageBillingAndDomains(user);

  return (
    <div className="app-page">
      <div className="mx-auto w-full max-w-6xl space-y-8">
        <SettingsHeader
          eyebrow={t("settings.systemLabel")}
          title={t("nav.settings")}
          description={t("settings.pageIntro")}
        />
        {showBilling ? <BillingSettingsContainer /> : null}
      </div>
    </div>
  );
}

// frontend/src/features/settings/pages/TenantResetPage.tsx
// Feladat: Tenant alaphelyzet külön oldal (ideiglenes menüpont, élesítés előtt levesszük).
// Sárközi Mihály - 2026.07.18

import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import { canResetTenant } from "../model/settingsPermissions";
import ResetSettingsContainer from "../sections/reset/ResetSettingsContainer";
import SettingsAccessDenied from "../shell/SettingsAccessDenied";
import SettingsHeader from "../shell/SettingsHeader";

export default function TenantResetPage() {
  const { t } = useTranslation();
  const { user } = useAuthStore();

  if (!canResetTenant(user)) return <SettingsAccessDenied message={t("settings.ownerOnly")} />;

  return (
    <div className="app-page">
      <div className="mx-auto w-full max-w-6xl space-y-8">
        <SettingsHeader
          eyebrow={t("settings.systemLabel")}
          title={t("nav.tenantReset")}
          description={t("settings.resetPageHint")}
        />
        <ResetSettingsContainer />
      </div>
    </div>
  );
}

from __future__ import annotations

# backend/apps/settings/service/locale_settings_service.py
# Feladat: Locale settings (timezone/date/time format) üzleti szolgáltatás a core settings réteghez.
# Sárközi Mihály - 2026.05.29

from dataclasses import dataclass

from apps.settings.domain.settings_state import LocaleSettingsState

# Egyelőre nincs UI a lokalizációhoz: mindig ezek az értékek érvényesek.
FIXED_LOCALE_SETTINGS = LocaleSettingsState(
    timezone="Europe/Budapest",
    date_format="YYYY-MM-DD",
    time_format="HH:mm",
)


@dataclass(frozen=True)
class LocaleSettingsUpdate:
    timezone: str | None = None
    date_format: str | None = None
    time_format: str | None = None


class LocaleSettingsService:
    def __init__(self, *, core_settings_service) -> None:
        self._core_settings_service = core_settings_service

    def get_locale_settings(self) -> LocaleSettingsState:
        return FIXED_LOCALE_SETTINGS

    def update_locale_settings(self, *, payload: LocaleSettingsUpdate, updated_by: int | None = None) -> LocaleSettingsState:
        # Modul megmarad, de a beállítás egyelőre nem változtatható.
        _ = payload, updated_by, self._core_settings_service
        return FIXED_LOCALE_SETTINGS


__all__ = ["FIXED_LOCALE_SETTINGS", "LocaleSettingsService", "LocaleSettingsUpdate"]

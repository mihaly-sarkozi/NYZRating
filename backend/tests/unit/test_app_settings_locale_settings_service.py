# backend/tests/unit/test_app_settings_locale_settings_service.py
# Feladat: LocaleSettingsService fixált locale értékeinek unit tesztje.
# Sárközi Mihály - 2026.05.29

from __future__ import annotations

import pytest

from apps.settings.service.locale_settings_service import FIXED_LOCALE_SETTINGS, LocaleSettingsService, LocaleSettingsUpdate

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


class _CoreSettings:
    def get_locale_settings(self) -> dict[str, str]:
        return {"timezone": "UTC", "date_format": "DD.MM.YYYY", "time_format": "HH:mm:ss"}

    def update_locale_settings(self, **kwargs) -> dict[str, str]:
        raise AssertionError(f"update should be disabled while locale is fixed: {kwargs}")


def test_get_locale_settings_returns_fixed_values() -> None:
    service = LocaleSettingsService(core_settings_service=_CoreSettings())
    response = service.get_locale_settings()
    assert response == FIXED_LOCALE_SETTINGS
    assert response.timezone == "Europe/Budapest"
    assert response.date_format == "YYYY-MM-DD"
    assert response.time_format == "HH:mm"


def test_locale_update_is_noop_and_returns_fixed_values() -> None:
    service = LocaleSettingsService(core_settings_service=_CoreSettings())

    response = service.update_locale_settings(
        payload=LocaleSettingsUpdate(
            timezone="UTC",
            date_format="DD.MM.YYYY",
            time_format="HH:mm:ss",
        ),
        updated_by=7,
    )

    assert response == FIXED_LOCALE_SETTINGS

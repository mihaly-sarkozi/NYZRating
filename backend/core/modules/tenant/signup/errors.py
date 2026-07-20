# backend/core/modules/tenant/signup/errors.py
# Feladat: A demo signup folyamat typed hibáit definiálja. Captcha, rate limit, consent, token, email és provisioning hibákat külön exceptionként ad, hogy a router tisztán mapelje HTTP válaszokra. Tenant signup error contract réteg.
# Sárközi Mihály - 2026.05.21

"""Tenant signup typed hibatípusok.

A TenantSignupOrchestrator (és use case-ek) typed exception-öket dobnak,
a route handler ezeket kapja el és mapeli HTTP státuszkódra –
string-alapú ValueError ellenőrzések helyett.
"""
from __future__ import annotations


class SignupError(Exception):
    """Alap signup hiba."""


class DemoSessionRequiredError(SignupError):
    """Demo signup esetén session azonosító szükséges."""


class InvalidSlugError(SignupError):
    """Érvényes slug nem generálható."""


class NameRequiredError(SignupError):
    """Név megadása kötelező."""


class DemoAlreadyExistsError(SignupError):
    """Ezzel az email-lel már létezik demo tenant."""


class BusinessAlreadyExistsError(SignupError):
    """Ez az üzlet (Google vélemény link) már regisztrálva van — visszakapcsolás szükséges."""

    def __init__(
        self,
        *,
        tenant_slug: str,
        login_url: str,
        is_active: bool = True,
        message: str | None = None,
    ) -> None:
        self.tenant_slug = tenant_slug
        self.login_url = login_url
        self.is_active = is_active
        super().__init__(message or "business_exists")


class DemoEmailBlockedError(SignupError):
    """Ez az email cím le van tiltva (korábbi leiratkozás miatt)."""


class DemoSignupDisabledError(SignupError):
    """Új demo signup ideiglenesen le van tiltva."""


class DemoSignupCapacityReachedError(SignupError):
    """A napi demo kapacitás vagy limit betelt."""


class DemoSignupRateLimitedError(SignupError):
    """IP/email/session alapú signup limit túllépve."""


class DemoSignupDisposableEmailError(SignupError):
    """Disposable email domain nem engedélyezett."""


class DemoSignupInvalidEmailDomainError(SignupError):
    """Email domain nem érvényes / nem kézbesíthető."""


class DemoSignupVerificationInvalidError(SignupError):
    """Email megerősítő token érvénytelen vagy hiányzik."""


class DemoSignupVerificationExpiredError(SignupError):
    """Email megerősítő token lejárt."""

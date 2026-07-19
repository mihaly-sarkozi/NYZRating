# backend/core/modules/tenant/router/tenant_router.py
# Feladat: A tenant onboarding és admin tenant HTTP API FastAPI adaptere. Demo signup, resend, unsubscribe, tenant lista és privacy PDF endpointokat köt service-ekhez, captcha és hibamapping logikával. Tenant router réteg.
# Sárközi Mihály - 2026.05.21

import logging
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.exc import SQLAlchemyError

from core.kernel.cache import redis_configured
from core.modules.tenant.dependencies import get_tenant_signup_service
from core.kernel.config.config_loader import settings
from core.kernel.config.config_loader import get_app_env
from core.kernel.config.environment import is_deployed_env
from core.kernel.security.rate_limit import limiter
from shared.utils.slug import slug_is_valid
from core.modules.tenant.router.requests import ConfirmSignupRequest, TenantSignupRequest
from core.modules.tenant.service import TenantSignupService
from core.modules.tenant.signup.errors import (
    DemoAlreadyExistsError,
    DemoSignupCapacityReachedError,
    DemoSignupDisabledError,
    DemoSignupDisposableEmailError,
    DemoEmailBlockedError,
    DemoSignupInvalidEmailDomainError,
    DemoSignupRateLimitedError,
    DemoSessionRequiredError,
    DemoSignupVerificationExpiredError,
    DemoSignupVerificationInvalidError,
    InvalidSlugError,
    NameRequiredError,
)
from lang.messages import lang_from_request

router = APIRouter()
_log = logging.getLogger(__name__)
_PRIVACY_POLICY_DIR = Path(__file__).resolve().parents[4] / "storage" / "legal"
_PRIVACY_POLICY_FILES = {
    "hu": ("adatkezelesi-tajekoztato.pdf", _PRIVACY_POLICY_DIR / "adatkezelesi-tajekoztato.hu.pdf"),
    "en": ("privacy-policy.pdf", _PRIVACY_POLICY_DIR / "privacy-policy.en.pdf"),
    "es": ("politica-de-privacidad.pdf", _PRIVACY_POLICY_DIR / "politica-de-privacidad.es.pdf"),
}


def _client_ip(request: Request) -> str:
    if request.client and request.client.host:
        return str(request.client.host).strip()[:64] or "unknown"
    return "unknown"


def _verify_signup_captcha_or_raise(request: Request, token: str | None) -> None:
    require_captcha = bool(getattr(settings, "demo_signup_require_captcha", False))
    provider = str(getattr(settings, "demo_signup_captcha_provider", "none") or "none").strip().lower()
    secret = str(getattr(settings, "demo_signup_captcha_secret", "") or "").strip()
    if not require_captcha:
        return
    if provider not in {"turnstile", "recaptcha"}:
        raise HTTPException(status_code=503, detail="Signup captcha provider is not configured.")
    if not secret:
        raise HTTPException(status_code=503, detail="Signup captcha secret is missing.")
    normalized_token = str(token or "").strip()
    if not normalized_token:
        raise HTTPException(status_code=400, detail="Captcha token required.")
    remote_ip = _client_ip(request)
    payload = urlencode({"secret": secret, "response": normalized_token, "remoteip": remote_ip}).encode("utf-8")
    verify_url = (
        "https://challenges.cloudflare.com/turnstile/v0/siteverify"
        if provider == "turnstile"
        else "https://www.google.com/recaptcha/api/siteverify"
    )
    try:
        req = UrlRequest(verify_url, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        with urlopen(req, timeout=5.0) as response:
            body = response.read().decode("utf-8", errors="replace")
        if '"success": true' in body or '"success":true' in body:
            return
    except Exception:
        pass
    raise HTTPException(status_code=400, detail="Captcha verification failed.")


def _ensure_demo_signup_redis_or_503() -> None:
    fail_closed = bool(getattr(settings, "demo_signup_fail_closed_without_redis", True))
    if not fail_closed:
        return
    try:
        env = get_app_env()
    except Exception:
        env = "dev"
    if not is_deployed_env(env):
        return
    if redis_configured():
        return
    raise HTTPException(
        status_code=503,
        detail="A demo regisztráció átmenetileg nem elérhető. Kérlek próbáld újra később.",
    )


# Ez a függvény a signup captcha nyilvános configját adja (site key nem titok).
@router.get("/installer/captcha-config")
@limiter.limit("60/minute")
def captcha_config(request: Request):
    require_captcha = bool(getattr(settings, "demo_signup_require_captcha", False))
    provider = str(getattr(settings, "demo_signup_captcha_provider", "none") or "none").strip().lower()
    site_key = (
        str(getattr(settings, "demo_signup_captcha_site_key", "") or "").strip()
        or str(os.getenv("VITE_TURNSTILE_SITE_KEY", "") or "").strip()
    )
    return {
        "required": require_captcha,
        "provider": provider,
        "site_key": site_key if require_captcha and provider in {"turnstile", "recaptcha"} else "",
    }


# Ez a függvény ellenőrzi a(z) slug logikáját.
@router.get("/installer/check-slug")
@limiter.limit("30/minute")
def check_slug(
    request: Request,
    slug: str = "",
    service: TenantSignupService = Depends(get_tenant_signup_service),
):
    slug = (slug or "").strip().lower()
    if not slug:
        return {"available": False, "slug": ""}
    if not slug_is_valid(slug):
        return {"available": False, "slug": slug}
    try:
        available = service.is_slug_available(slug)
    except SQLAlchemyError as exc:
        _log.exception("installer check-slug DB error: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Az ellenőrzés ideiglenesen nem elérhető. Próbáld később.",
        )
    return {
        "available": available,
        "slug": slug,
        "tenant_base_domain": settings.tenant_base_domain,
    }


# Ez a függvény a(z) tenant_signup logikáját valósítja meg.
@router.post("/installer/tenant-signup")
@limiter.limit("100/minute")
def tenant_signup(
    request: Request,
    body: TenantSignupRequest,
    service: TenantSignupService = Depends(get_tenant_signup_service),
):
    _ensure_demo_signup_redis_or_503()
    email = (body.email or "").strip()
    name = (body.name or "").strip()
    company_name = (body.company_name or "").strip() or name
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Érvényes email szükséges.")
    if not company_name:
        raise HTTPException(status_code=400, detail="A cégnév kötelező.")
    _verify_signup_captcha_or_raise(request, body.captcha_token)
    _DEMO_EXISTS_DETAIL = {
        "reason": "demo_exists",
        "message": (
            "Ezzel az email címmel már indítottál demo regisztrációt. "
            "Ha szeretnél új linket, elküldjük újra."
        ),
    }
    try:
        result = service.signup(
            email=email,
            kb_name=(body.kb_name or "").strip() or None,
            name=name or company_name,
            locale=(body.locale or "").strip().lower() or None,
            resend_existing_access=body.resend_existing_access,
            company_name=company_name,
            address=(body.address or "").strip() or None,
            phone=(body.phone or "").strip() or None,
            plan_code=(body.plan_code or "free").strip().lower() or "free",
            subscription_period=(body.billing_period or "monthly").strip().lower() or "monthly",
            demo_session_id=(body.demo_session_id or "").strip() or None,
            remote_ip=_client_ip(request),
        )
    except DemoSessionRequiredError:
        raise HTTPException(status_code=400, detail="Hiányzik a demo session azonosító.")
    except InvalidSlugError:
        raise HTTPException(status_code=400, detail="Nem sikerült érvényes tenant nevet generálni.")
    except NameRequiredError:
        raise HTTPException(status_code=400, detail="A név kötelező.")
    except DemoAlreadyExistsError:
        raise HTTPException(status_code=409, detail=_DEMO_EXISTS_DETAIL)
    except DemoSignupVerificationExpiredError:
        raise HTTPException(
            status_code=410,
            detail={
                "reason": "expired",
                "message": "A megerősítő link lejárt. Indítsd újra a regisztrációt.",
            },
        )
    except DemoSignupVerificationInvalidError:
        raise HTTPException(
            status_code=400,
            detail={
                "reason": "invalid",
                "message": "Nincs folyamatban lévő megerősítendő regisztráció ehhez az emailhez.",
            },
        )
    except DemoEmailBlockedError:
        raise HTTPException(
            status_code=403,
            detail=(
                "Figyelem! Ezzel az email címmel nem hozható létre új demo regisztráció. "
                "A korábbi leiratkozás miatt a demo hozzáférés tiltva van."
            ),
        )
    except DemoSignupDisabledError:
        raise HTTPException(
            status_code=503,
            detail="Az új demo regisztrációk jelenleg szünetelnek. Add meg az email címed, és hamarosan jelentkezünk.",
        )
    except DemoSignupDisposableEmailError:
        raise HTTPException(status_code=400, detail="Egyszer használatos email domainnel demo regisztráció nem engedélyezett.")
    except DemoSignupInvalidEmailDomainError:
        raise HTTPException(status_code=400, detail="Az email domain nem érvényes vagy nem fogad levelet.")
    except DemoSignupCapacityReachedError:
        raise HTTPException(
            status_code=429,
            detail=(
                "A mai demo kapacitás betelt, add meg az email címed, "
                "és küldünk hozzáférést."
            ),
        )
    except DemoSignupRateLimitedError:
        raise HTTPException(status_code=429, detail="Túl sok demo regisztrációs próbálkozás erről a forrásról.")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc) or "A regisztráció ideiglenesen nem elérhető.")

    return {
        "slug": result.slug,
        "message": (
            "Elküldtük a megerősítő emailt. Nyisd meg a linket az emailben, majd állítsd be a jelszavad."
            if getattr(result, "awaiting_email_verification", False)
            else (
                "A demo környezet elkészült. Emailben küldtünk egy jelszóbeállító linket."
                if result.created_new
                else "A jelszóbeállító linket újra elküldtük emailben."
            )
        ),
        "host_hint": result.host_hint,
        "demo_login_token": (
            result.demo_login_token
            if bool(getattr(settings, "demo_signup_expose_login_token_in_response", False))
            else None
        ),
        "created_new": result.created_new,
        "resent_existing": result.resent_existing,
        "awaiting_email_verification": bool(getattr(result, "awaiting_email_verification", False)),
    }


@router.post("/installer/confirm-signup")
@limiter.limit("10/minute")
def confirm_signup(
    request: Request,
    body: ConfirmSignupRequest,
    service: TenantSignupService = Depends(get_tenant_signup_service),
):
    """Email megerősítés → tenant provision → set-password URL a tenant hoston."""
    token = str(body.token or "").strip()
    if not token:
        raise HTTPException(
            status_code=400,
            detail={"reason": "missing", "message": "Hiányzik a megerősítő token."},
        )
    try:
        result = service.confirm_signup(token=token)
    except DemoSignupVerificationExpiredError:
        raise HTTPException(
            status_code=410,
            detail={
                "reason": "expired",
                "message": "A megerősítő link lejárt. Indítsd újra a regisztrációt.",
            },
        )
    except DemoSignupVerificationInvalidError:
        raise HTTPException(
            status_code=400,
            detail={
                "reason": "invalid",
                "message": "A megerősítő link érvénytelen vagy már felhasználták.",
            },
        )
    except SQLAlchemyError as exc:
        _log.exception("installer confirm-signup DB error: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="A megerősítés ideiglenesen nem elérhető. Próbáld később.",
        )
    return {
        "slug": result.slug,
        "host_hint": result.host_hint,
        "email": result.email,
        "set_password_url": result.set_password_url,
        "message": "Az email címed megerősítve. Most állítsd be a jelszavad.",
    }


@router.get("/installer/demo-login/resolve")
@limiter.limit("20/minute")
def resolve_demo_login(
    request: Request,
    token: str = "",
    service: TenantSignupService = Depends(get_tenant_signup_service),
):
    if not token:
        raise HTTPException(status_code=400, detail={"reason": "missing", "message": "Hiányzik a demo token."})
    try:
        redirect_to = service.resolve_demo_login_redirect(token)
    except ValueError as exc:
        if str(exc) == "demo_token_expired":
            raise HTTPException(status_code=410, detail={"reason": "expired", "message": "A demo link lejárt."})
        raise HTTPException(status_code=400, detail={"reason": "invalid", "message": "A demo link érvénytelen."})
    return {"redirect_to": redirect_to}


@router.get("/installer/privacy-policy.pdf")
def installer_privacy_policy(request: Request, lang: str | None = None):
    lang = (lang or "").strip().lower()[:2] or lang_from_request(request)
    if lang not in _PRIVACY_POLICY_FILES:
        lang = "hu"
    filename, path = _PRIVACY_POLICY_FILES[lang]
    if not path.exists():
        raise HTTPException(status_code=404, detail="A PDF nem található.")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=filename,
    )

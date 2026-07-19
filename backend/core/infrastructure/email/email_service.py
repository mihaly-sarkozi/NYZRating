# backend/core/infrastructure/email/email_service.py
# Feladat: SMTP alapú email küldési infrastruktúra service-t és dev-log
# maszkoló helper logikát ad. Validálja a címzett/feladó címet, SMTP
# hiányában érzékeny tokeneket maszkolt preview-ként logol, production
# küldésnél TLS/SSL SMTP-t használ, és 2FA, set-password, demo login,
# demo set-password és demo signup sablonküldő façade metódusokat biztosít.
# Core email adapter auth, users, tenant signup és platform admin folyamatokhoz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import re
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid, parseaddr
from typing import Optional

from core.kernel.config.config_loader import settings
from core.kernel.logging.observability import log_structured_event
from lang.email_templates import (
    DEFAULT_LANG,
    get_2fa_token_block,
    get_email_template,
)

# Maximális body hossz a dev log preview-ban, maszkolás után.
_DEV_LOG_BODY_PREVIEW_LEN = 280

# Egyszerű, infrastruktúraszintű email-validáció.
# A részletes felhasználói validáció továbbra is az alkalmazási réteg feladata.
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def mask_email_body_for_log(
    body: str,
    max_len: int = _DEV_LOG_BODY_PREVIEW_LEN,
) -> str:
    """
    Érzékeny részek maszkolása, hogy a fejlesztői email-log ne
    tartalmazzon 2FA-kódot, pending tokent vagy linktokent.

    Visszatérési érték:
        Maszkolt szöveg legfeljebb max_len hosszúságban. Ha az eredeti
        tartalom hosszabb, a végére az eredeti hossz kerül.
    """
    if not body:
        return ""

    masked = str(body)

    # URL-paraméterben található token maszkolása.
    masked = re.sub(
        r"([?&]token=)([^&\s\"'<>]+)",
        r"\1[REDACTED]",
        masked,
        flags=re.IGNORECASE,
    )

    # Hatjegyű 2FA-kód.
    masked = re.sub(r"\b\d{6}\b", "******", masked)

    # Hosszú hexadecimális vagy alfanumerikus token.
    masked = re.sub(
        r"\b[a-zA-Z0-9_-]{20,}\b",
        "[REDACTED]",
        masked,
    )

    if len(masked) > max_len:
        return (
            masked[:max_len].rstrip()
            + f" ... ({len(body)} chars)"
        )

    return masked


def _normalize_email(value: str | None) -> str:
    """Email-cím kinyerése és normalizálása névvel ellátott címből is."""
    parsed = parseaddr((value or "").strip())[1]
    return parsed.strip().lower()


def _is_valid_email(value: str) -> bool:
    """Alapvető email-formátum ellenőrzés."""
    return bool(value and _EMAIL_PATTERN.fullmatch(value))


def _as_bool(value: object, default: bool = False) -> bool:
    """Biztonságos bool konverzió settings vagy env eredetű értékhez."""
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    normalized = str(value).strip().lower()

    if normalized in {"1", "true", "yes", "on"}:
        return True

    if normalized in {"0", "false", "no", "off", ""}:
        return False

    return default


class EmailService:
    """Email-küldési szolgáltatás SMTP kapcsolaton keresztül."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        use_tls: Optional[bool] = None,
        use_ssl: Optional[bool] = None,
    ) -> None:
        self.host = (host or settings.smtp_host or "").strip()
        self.port = int(port or settings.smtp_port or 587)
        self.user = (user or settings.smtp_user or "").strip()
        self.password = (
            password
            if password is not None
            else settings.smtp_password
        )
        self.password = (self.password or "").strip()

        self.from_email = (
            from_email or settings.smtp_from_email or ""
        ).strip()

        self.from_name = (
            from_name
            or settings.smtp_from_name
            or self.from_email
            or "NYZRating"
        ).strip()

        configured_tls = getattr(settings, "smtp_use_tls", True)
        configured_ssl = getattr(settings, "smtp_use_ssl", False)

        self.use_tls = (
            _as_bool(configured_tls, default=True)
            if use_tls is None
            else bool(use_tls)
        )
        self.use_ssl = (
            _as_bool(configured_ssl, default=False)
            if use_ssl is None
            else bool(use_ssl)
        )

    def _build_message(
        self,
        *,
        to_email: str,
        from_email: str,
        subject: str,
        body: str,
        is_html: bool,
    ) -> EmailMessage:
        """Szabványos MIME email összeállítása megfelelő fejlécekkel."""
        message = EmailMessage()

        message["Subject"] = str(subject or "").strip()
        message["From"] = formataddr(
            (self.from_name or "NYZRating", from_email)
        )
        message["To"] = to_email
        message["Reply-To"] = from_email
        message["Date"] = formatdate(localtime=False)
        message["Message-ID"] = make_msgid(domain="nyzrating.com")

        if is_html:
            # A plain-text rész fontos a kézbesíthetőség és a csak
            # szöveget támogató levelezőprogramok miatt.
            plain_fallback = (
                "Ez az üzenet HTML formátumú.\n\n"
                "A teljes tartalom megtekintéséhez nyisd meg egy "
                "HTML-emailt támogató levelezőprogramban."
            )
            message.set_content(
                plain_fallback,
                subtype="plain",
                charset="utf-8",
            )
            message.add_alternative(
                body or "",
                subtype="html",
                charset="utf-8",
            )
        else:
            message.set_content(
                body or "",
                subtype="plain",
                charset="utf-8",
            )

        return message

    def _open_smtp_connection(
        self,
    ) -> smtplib.SMTP | smtplib.SMTP_SSL:
        """
        SMTP-kapcsolat létrehozása.

        SMTP_USE_SSL=true:
            Közvetlen TLS-kapcsolat, jellemzően 465-ös porton.

        SMTP_USE_TLS=true:
            Normál SMTP, majd STARTTLS, jellemzően 587-es porton.
        """
        tls_context = ssl.create_default_context()

        if self.use_ssl:
            server: smtplib.SMTP | smtplib.SMTP_SSL = (
                smtplib.SMTP_SSL(
                    self.host,
                    self.port,
                    timeout=30,
                    context=tls_context,
                )
            )
            server.ehlo()
            return server

        server = smtplib.SMTP(
            self.host,
            self.port,
            timeout=30,
        )
        server.ehlo()

        if self.use_tls:
            server.starttls(context=tls_context)
            server.ehlo()

        return server

    def _login(self, server: smtplib.SMTP | smtplib.SMTP_SSL) -> None:
        """
        SMTP-hitelesítés.

        A szóköz nélküli jelszóval történő második próbálkozás megmarad
        a Gmail app-password kompatibilitás miatt.
        """
        try:
            server.login(self.user, self.password)
        except smtplib.SMTPAuthenticationError:
            password_without_spaces = self.password.replace(" ", "")

            if password_without_spaces == self.password:
                raise

            server.login(
                self.user,
                password_without_spaces,
            )

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        is_html: bool = False,
    ) -> bool:
        """
        Email küldése.

        Visszatérési érték:
            True: az SMTP-szerver elfogadta az üzenetet.
            False: validációs, konfigurációs vagy SMTP-hiba történt.

        Fontos:
            A True nem garantálja a végső postaládába történő
            kézbesítést. Azt jelenti, hogy az SMTP-szerver átvette
            az üzenetet további kézbesítésre.
        """
        normalized_to_email = _normalize_email(to_email)
        normalized_from_email = _normalize_email(self.from_email)

        if not _is_valid_email(normalized_to_email):
            log_structured_event(
                "core.email",
                "email.invalid_recipient",
                level=40,
                to_email=to_email,
                subject=subject,
            )
            return False

        if not _is_valid_email(normalized_from_email):
            log_structured_event(
                "core.email",
                "email.invalid_sender",
                level=40,
                from_email=self.from_email,
                subject=subject,
            )
            return False

        smtp_is_configured = bool(
            self.host
            and self.port
            and self.user
            and self.password
        )

        if not smtp_is_configured:
            from core.kernel.config.config_loader import get_app_env
            from core.kernel.config.environment import (
                is_local_env,
                is_test_env,
            )

            try:
                env = get_app_env()
            except Exception:
                env = "local"

            allow_simulation = is_test_env(env) or (
                is_local_env(env)
                and not bool(
                    getattr(settings, "cookie_secure", False)
                )
            )

            preview = mask_email_body_for_log(body)

            log_structured_event(
                "core.email",
                (
                    "email.simulated"
                    if allow_simulation
                    else "email.smtp_not_configured"
                ),
                to_email=normalized_to_email,
                from_email=normalized_from_email,
                subject=subject,
                body_preview=preview,
                smtp_configured=False,
                level=30 if allow_simulation else 40,
            )

            return bool(allow_simulation)

        try:
            message = self._build_message(
                to_email=normalized_to_email,
                from_email=normalized_from_email,
                subject=subject,
                body=body,
                is_html=is_html,
            )

            with self._open_smtp_connection() as server:
                self._login(server)

                refused_recipients = server.send_message(
                    message,
                    from_addr=normalized_from_email,
                    to_addrs=[normalized_to_email],
                )

                if refused_recipients:
                    raise smtplib.SMTPRecipientsRefused(
                        refused_recipients
                    )

            log_structured_event(
                "core.email",
                "email.sent",
                to_email=normalized_to_email,
                from_email=normalized_from_email,
                subject=subject,
                smtp_host=self.host,
                smtp_port=self.port,
                smtp_tls=self.use_tls,
                smtp_ssl=self.use_ssl,
            )

            return True

        except smtplib.SMTPRecipientsRefused as exc:
            log_structured_event(
                "core.email",
                "email.recipient_refused",
                level=40,
                to_email=normalized_to_email,
                from_email=normalized_from_email,
                subject=subject,
                error=str(exc),
                smtp_host=self.host or None,
                smtp_port=self.port,
            )
            return False

        except smtplib.SMTPAuthenticationError as exc:
            log_structured_event(
                "core.email",
                "email.authentication_failed",
                level=40,
                to_email=normalized_to_email,
                from_email=normalized_from_email,
                subject=subject,
                error=str(exc),
                smtp_host=self.host or None,
                smtp_port=self.port,
            )
            return False

        except (
            smtplib.SMTPException,
            OSError,
            TimeoutError,
            ssl.SSLError,
        ) as exc:
            log_structured_event(
                "core.email",
                "email.send_failed",
                level=40,
                to_email=normalized_to_email,
                from_email=normalized_from_email,
                subject=subject,
                error=str(exc),
                error_type=type(exc).__name__,
                smtp_host=self.host or None,
                smtp_port=self.port,
                smtp_tls=self.use_tls,
                smtp_ssl=self.use_ssl,
            )
            return False

        except Exception as exc:
            # Stabil eseménynév a monitorozáshoz. A felhasználói
            # hibaüzenetet a felsőbb alkalmazási/router réteg lokalizálja.
            log_structured_event(
                "core.email",
                "email.send_failed",
                level=40,
                to_email=normalized_to_email,
                from_email=normalized_from_email,
                subject=subject,
                error=str(exc),
                error_type=type(exc).__name__,
                smtp_host=self.host or None,
                smtp_port=self.port,
            )
            return False

    def send_2fa_code(
        self,
        to_email: str,
        code: str,
        pending_token: str | None = None,
        lang: str | None = None,
        expiry_minutes: int = 10,
    ) -> bool:
        """
        Kétfaktoros kód és opcionális pending token küldése.
        A szöveg lokalizált sablonból készül.
        """
        token_block = get_2fa_token_block(
            pending_token or "",
            lang=lang,
        )

        subject, body = get_email_template(
            "2fa",
            lang=lang or DEFAULT_LANG,
            code=code,
            token_block=token_block,
            expiry_minutes=expiry_minutes,
        )

        return self.send_email(
            to_email,
            subject,
            body,
        )

    def send_set_password_invite(
        self,
        to_email: str,
        set_password_link: str,
        lang: str | None = None,
    ) -> bool:
        """Jelszóbeállítási meghívó küldése."""
        subject, body = get_email_template(
            "set_password",
            lang=lang or DEFAULT_LANG,
            set_password_link=set_password_link,
        )

        return self.send_email(
            to_email,
            subject,
            body,
        )

    def send_email_change_confirmation(
        self,
        to_email: str,
        confirm_email_link: str,
        *,
        current_email: str,
        new_email: str,
        lang: str | None = None,
    ) -> bool:
        """Email-cím módosításának megerősítése."""
        subject, body = get_email_template(
            "confirm_email_change",
            lang=lang or DEFAULT_LANG,
            current_email=current_email,
            new_email=new_email,
            confirm_email_link=confirm_email_link,
        )

        return self.send_email(
            to_email,
            subject,
            body,
        )

    def send_demo_login_link(
        self,
        to_email: str,
        demo_login_link: str,
        *,
        demo_expires_at: datetime,
        lang: str | None = None,
    ) -> bool:
        """Demo belépési link küldése."""
        subject, body = get_email_template(
            "demo_login",
            lang=lang or DEFAULT_LANG,
            demo_login_link=demo_login_link,
            demo_expires_at=demo_expires_at.strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            ),
        )

        return self.send_email(
            to_email,
            subject,
            body,
        )

    def send_demo_set_password_invite(
        self,
        to_email: str,
        set_password_link: str,
        *,
        demo_expires_at: datetime,
        lang: str | None = None,
    ) -> bool:
        """Demo felhasználói jelszóbeállítási meghívó küldése."""
        subject, body = get_email_template(
            "demo_set_password",
            lang=lang or DEFAULT_LANG,
            set_password_link=set_password_link,
            demo_expires_at=demo_expires_at.strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            ),
        )

        return self.send_email(
            to_email,
            subject,
            body,
        )

    def send_demo_confirm_signup(
        self,
        to_email: str,
        confirm_signup_link: str,
        *,
        tenant_slug: str,
        lang: str | None = None,
    ) -> bool:
        """Demo-regisztráció email-címének megerősítése."""
        subject, body = get_email_template(
            "demo_confirm_signup",
            lang=lang or DEFAULT_LANG,
            confirm_signup_link=confirm_signup_link,
            tenant_slug=tenant_slug,
        )

        return self.send_email(
            to_email,
            subject,
            body,
        )


__all__ = [
    "EmailService",
    "mask_email_body_for_log",
]
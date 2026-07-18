#!/usr/bin/env python3
"""
Production config validator smoke test.

Ellenőrzi, hogy a settings_production_validators.py:
  1. Importálható (nincs szintaxishiba)
  2. A validator függvények aláírása helyes (fogadják a settings paramétert)
  3. Futtatható egy minimális prod-szerű settings mock-kal (nem dob NameError-t)
"""
from __future__ import annotations

import inspect
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

try:
    from core.kernel.config import settings_production_validators as spv

    print("✓ Import OK")
except ImportError as exc:
    print(f"✗ Import hiba: {exc}")
    raise SystemExit(1) from exc

sig = inspect.signature(spv.validate_production_security_settings)
params = list(sig.parameters)
assert "settings" in params, (
    f"✗ validate_production_security_settings() nem vesz fel 'settings' paramétert: {params}"
)
print("✓ Aláírás OK")

debug_sig = inspect.signature(spv._validate_production_debug_bypass_env)
debug_params = list(debug_sig.parameters)
assert "settings" in debug_params, (
    f"✗ _validate_production_debug_bypass_env() nem vesz fel 'settings' paramétert: {debug_params}"
)
print("✓ Debug bypass aláírás OK")

mock_settings = types.SimpleNamespace(
    cors_origins="https://app.example.com",
    frontend_base_url="https://app.example.com",
    smtp_password="secret",
    smtp_host="smtp.example.com",
    smtp_user="user@example.com",
    smtp_from_email="noreply@example.com",
    smtp_from_name="NYZRating",
    database_url="postgresql+psycopg2://user:pass@db/nyzrating",
    cookie_secure=True,
    trusted_hosts="app.example.com",
    tenant_base_domain="app.example.com",
    password_security_level="standard",
    rate_limit_login_per_minute=10,
    jwt_issuer="https://app.example.com",
    jwt_audience="https://api.example.com",
    redis_url="redis://localhost:6379/0",
    access_ttl_min=15,
    embedding_provider="local",
    embedding_allow_dummy=False,
)

os.environ["JWT_SECRET"] = "a" * 64
os.environ["APP_ENV"] = "production"
os.environ.pop("DISABLE_CSRF", None)
os.environ.pop("BILLING_DEBUG_ROUTES_ENABLED", None)
os.environ.pop("BILLING_DISABLED", None)
os.environ["BILLING_PROVIDER"] = "manual"
os.environ["BILLING_MODE"] = "manual"
os.environ.pop("PII_ALLOW_LEGACY_PLAINTEXT_READ", None)

try:
    spv.validate_production_security_settings(mock_settings, env="production")
    print("✓ Production validator NameError-mentes (prod env smoke OK)")
except NameError as exc:
    print(f"✗ NameError a production validátorban: {exc}")
    print("  Egy belső függvény olyan változóra hivatkozik, amit nem kapott paraméterként.")
    raise SystemExit(1) from exc
except ValueError as exc:
    print(f"  (ValueError a validátortól – normális ha a mock hiányos: {exc})")
    print("✓ NameError nincs – a validator szintaktikailag helyes")

print("\nMinden ellenőrzés átment.")

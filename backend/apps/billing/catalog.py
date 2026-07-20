# backend/apps/billing/catalog.py
# Feladat: A billing catalog alap seed adatait és catalog transzformációit tartalmazza. Plan/addon mapet és API response listát épít ORM sorokból, hogy a BillingService ne hordozza a statikus csomagdefiníciókat. Program-specifikus billing catalog helper réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from apps.billing.calculations import money
from apps.billing.domain import BillingAddon, BillingPlan
from apps.billing.models import DEFAULT_CURRENCY, BillingCatalogEntryORM
from apps.billing.schemas import BillingCatalogEntryResponse


def default_catalog_rows() -> list[dict[str, Any]]:
    """NYZ Rating csomagok: 1 teszt + 3 fizetős, csak kimenő megkeresésszám limittel.

    Árak HUF-ban (price_cents = Ft * 100). A questions_monthly = megkeresés / hó
    (tesztidőszakban SMS megkeresés).
    """
    return [
        {
            "entry_type": "plan",
            "code": "free",
            "name": "Teszt",
            "currency": DEFAULT_CURRENCY,
            "price_cents": 0,
            "included": {
                "questions_monthly": 3,
                "trial_days": 7,
            },
            "metadata_json": {
                "description": "1 hétig érvényes tesztidőszak",
                "kind": "outbound_inquiries",
            },
            "is_active": True,
        },
        {
            "entry_type": "plan",
            "code": "starter",
            "name": "Starter",
            "currency": DEFAULT_CURRENCY,
            "price_cents": 890_000,
            "included": {
                "questions_monthly": 40,
                "trial_days": 0,
            },
            "metadata_json": {
                "description": "Alap megkereséskeret",
                "kind": "outbound_inquiries",
            },
            "is_active": True,
        },
        {
            "entry_type": "plan",
            "code": "pro",
            "name": "Pro",
            "currency": DEFAULT_CURRENCY,
            "price_cents": 1_890_000,
            "included": {
                "questions_monthly": 150,
                "trial_days": 0,
            },
            "metadata_json": {
                "description": "Nagyobb megkereséskeret",
                "kind": "outbound_inquiries",
            },
            "is_active": True,
        },
        {
            "entry_type": "plan",
            "code": "growth",
            "name": "Pro (legacy)",
            "currency": DEFAULT_CURRENCY,
            "price_cents": 1_890_000,
            "included": {
                "questions_monthly": 150,
                "trial_days": 0,
            },
            "metadata_json": {
                "description": "Legacy alias – replaced by pro",
                "kind": "outbound_inquiries",
            },
            "is_active": False,
        },
        {
            "entry_type": "plan",
            "code": "business",
            "name": "Giga",
            "currency": DEFAULT_CURRENCY,
            "price_cents": 3_490_000,
            "included": {
                "questions_monthly": 400,
                "trial_days": 0,
            },
            "metadata_json": {
                "description": "Nagyforgalom esetén",
                "kind": "outbound_inquiries",
            },
            "is_active": True,
        },
        {
            "entry_type": "addon",
            "code": "question_pack_50",
            "name": "50 extra SMS",
            "currency": DEFAULT_CURRENCY,
            "price_cents": 590_000,
            "included": {"questions": 50},
            "metadata_json": {"carryover": True, "kind": "questions"},
            "is_active": True,
        },
        {
            "entry_type": "addon",
            "code": "question_pack_100",
            "name": "100 extra SMS (legacy)",
            "currency": DEFAULT_CURRENCY,
            "price_cents": 800_000,
            "included": {"questions": 100},
            "metadata_json": {"carryover": True, "kind": "questions"},
            "is_active": False,
        },
        {
            "entry_type": "addon",
            "code": "question_pack_500",
            "name": "500 extra SMS (legacy)",
            "currency": DEFAULT_CURRENCY,
            "price_cents": 500,
            "included": {"questions": 500},
            "metadata_json": {"carryover": True, "kind": "questions"},
            "is_active": False,
        },
        # Legacy addons – inaktívak, hogy a seed kikapcsolja a régi KB/tárhely/tanítás bővítőket
        {
            "entry_type": "addon",
            "code": "extra_kb",
            "name": "Extra tudástár / hó",
            "currency": DEFAULT_CURRENCY,
            "price_cents": 500,
            "included": {"knowledge_bases": 1},
            "metadata_json": {"recurring": True, "kind": "knowledge_bases"},
            "is_active": False,
        },
        {
            "entry_type": "addon",
            "code": "extra_storage_gb",
            "name": "Extra tárhely GB / hó",
            "currency": DEFAULT_CURRENCY,
            "price_cents": 500,
            "included": {"storage_gb": 1},
            "metadata_json": {"recurring": True, "kind": "storage_gb"},
            "is_active": False,
        },
        {
            "entry_type": "addon",
            "code": "training_initial_500k",
            "name": "Első betanítás",
            "currency": DEFAULT_CURRENCY,
            "price_cents": 0,
            "included": {"training_chars": 0},
            "metadata_json": {"recurring": False, "kind": "training_chars"},
            "is_active": False,
        },
        {
            "entry_type": "addon",
            "code": "training_extra_500k",
            "name": "További betanítás",
            "currency": DEFAULT_CURRENCY,
            "price_cents": 0,
            "included": {"training_chars": 0},
            "metadata_json": {"recurring": False, "kind": "training_chars"},
            "is_active": False,
        },
        {
            "entry_type": "discount",
            "code": "quarterly_7",
            "name": "Negyedéves kedvezmény",
            "currency": DEFAULT_CURRENCY,
            "price_cents": 0,
            "included": {},
            "metadata_json": {"billing_period": "quarterly", "discount_percent": 7},
            "is_active": True,
        },
        {
            "entry_type": "discount",
            "code": "yearly_15",
            "name": "Éves kedvezmény",
            "currency": DEFAULT_CURRENCY,
            "price_cents": 0,
            "included": {},
            "metadata_json": {"billing_period": "yearly", "discount_percent": 15},
            "is_active": True,
        },
    ]


def plan_map_from_catalog(rows: Iterable[BillingCatalogEntryORM]) -> dict[str, BillingPlan]:
    result: dict[str, BillingPlan] = {}
    for row in rows:
        if row.entry_type != "plan":
            continue
        included = dict(row.included or {})
        result[row.code] = BillingPlan(
            code=row.code,
            name=row.name,
            price_cents=int(row.price_cents or 0),
            included_kbs=int(included.get("knowledge_bases") or 0),
            included_storage_gb=int(included.get("storage_gb") or 0),
            included_questions_monthly=int(included.get("questions_monthly") or 0),
            max_users=(int(included["max_users"]) if included.get("max_users") is not None else None),
            trial_days=int(included.get("trial_days") or 0),
            included_training_chars=int(included.get("training_chars") or 0),
        )
    return result


def addon_map_from_catalog(rows: Iterable[BillingCatalogEntryORM]) -> dict[str, BillingAddon]:
    result: dict[str, BillingAddon] = {}
    for row in rows:
        if row.entry_type != "addon":
            continue
        result[row.code] = BillingAddon(
            code=row.code,
            name=row.name,
            price_cents=int(row.price_cents or 0),
            metadata={**dict(row.included or {}), **dict(row.metadata_json or {})},
        )
    return result


def catalog_response_from_rows(rows: Iterable[BillingCatalogEntryORM]) -> list[BillingCatalogEntryResponse]:
    return [
        BillingCatalogEntryResponse(
            entry_type=row.entry_type,
            code=row.code,
            name=row.name,
            currency=row.currency,
            price_cents=int(row.price_cents or 0),
            price=money(int(row.price_cents or 0)),
            included=dict(row.included or {}),
            metadata=dict(row.metadata_json or {}),
        )
        for row in rows
    ]


__all__ = [
    "addon_map_from_catalog",
    "catalog_response_from_rows",
    "default_catalog_rows",
    "plan_map_from_catalog",
]

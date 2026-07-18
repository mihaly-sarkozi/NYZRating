from __future__ import annotations

from dataclasses import dataclass

from apps.kb.kb_discovery.gazetteers.data_paths import data_file
from apps.kb.kb_discovery.gazetteers.loaders import load_csv_rows


@dataclass(frozen=True)
class AddressTypeEntry:
    alias: str
    kind: str
    language: str


class AddressTypeGazetteer:
    """Címtípus szótár (pl. utca/út/tér; street/road/avenue; calle/avenida).

    Forrás: `data/address_types/address_types.csv`. A `kind` kulcs az
    egységesített típuscímke (street, road, avenue, square, boulevard, ...).
    """

    _CSV = ("address_types", "address_types.csv")

    def __init__(self) -> None:
        rows = load_csv_rows(data_file(*self._CSV))
        entries: list[AddressTypeEntry] = []
        for row in rows:
            alias = (row.get("alias") or "").strip()
            kind = (row.get("kind") or "").strip().lower()
            language = (row.get("language") or "").strip().lower()
            if not alias or not kind:
                continue
            entries.append(AddressTypeEntry(alias=alias, kind=kind, language=language))
        self._entries = entries
        self._by_language: dict[str, list[AddressTypeEntry]] = {}
        for entry in entries:
            if entry.language:
                self._by_language.setdefault(entry.language, []).append(entry)

    def all_entries(self) -> list[AddressTypeEntry]:
        return list(self._entries)

    def entries_for_language(self, language_code: str | None) -> list[AddressTypeEntry]:
        code = (language_code or "").strip().lower()
        if code in self._by_language:
            return list(self._by_language[code])
        return list(self._entries)

    def aliases_for_language(self, language_code: str | None) -> list[str]:
        return [entry.alias for entry in self.entries_for_language(language_code)]


__all__ = ["AddressTypeEntry", "AddressTypeGazetteer"]

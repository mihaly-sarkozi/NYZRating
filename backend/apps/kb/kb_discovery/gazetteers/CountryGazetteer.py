from __future__ import annotations

from dataclasses import dataclass

from apps.kb.kb_discovery.gazetteers.data_paths import data_file
from apps.kb.kb_discovery.gazetteers.loaders import load_csv_rows


@dataclass(frozen=True)
class CountryEntry:
    canonical_name: str
    alias: str
    language: str
    iso_alpha2: str
    is_european: bool


class CountryGazetteer:
    """Országlista gazetteer.

    Forrás: `data/countries/countries.csv`. Minden alias-canonical-language tripletet
    külön sorként kezel, így ugyanaz az ország több aliassal és nyelvvel is szerepel.
    """

    _CSV = ("countries", "countries.csv")

    def __init__(self) -> None:
        rows = load_csv_rows(data_file(*self._CSV))
        entries: list[CountryEntry] = []
        for row in rows:
            canonical = (row.get("canonical_name") or "").strip()
            alias = (row.get("alias") or "").strip()
            language = (row.get("language") or "").strip().lower()
            iso = (row.get("iso_alpha2") or "").strip().upper()
            is_european = (row.get("is_european") or "").strip().lower() == "true"
            if not canonical or not alias:
                continue
            entries.append(
                CountryEntry(
                    canonical_name=canonical,
                    alias=alias,
                    language=language,
                    iso_alpha2=iso,
                    is_european=is_european,
                )
            )
        self._entries = entries
        self._by_language: dict[str, list[CountryEntry]] = {}
        for entry in entries:
            if entry.language:
                self._by_language.setdefault(entry.language, []).append(entry)

    def all_entries(self) -> list[CountryEntry]:
        return list(self._entries)

    def entries_for_language(self, language_code: str | None) -> list[CountryEntry]:
        code = (language_code or "").strip().lower()
        if code in self._by_language:
            return list(self._by_language[code])
        return list(self._entries)


__all__ = ["CountryEntry", "CountryGazetteer"]

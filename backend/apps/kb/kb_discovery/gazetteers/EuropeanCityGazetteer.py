from __future__ import annotations

from dataclasses import dataclass

from apps.kb.kb_discovery.gazetteers.data_paths import data_file
from apps.kb.kb_discovery.gazetteers.loaders import load_csv_rows


@dataclass(frozen=True)
class CityEntry:
    canonical_name: str
    alias: str
    language: str
    country_iso: str
    kind: str


class EuropeanCityGazetteer:
    """Európai város gazetteer (fővárosok és nagyobb városok).

    Forrás: `data/cities/european_cities.csv`. Minden alias külön sor, többféle
    nyelvi verzióval (pl. Vienna / Bécs / Wien / Viena).
    """

    _CSV = ("cities", "european_cities.csv")

    def __init__(self) -> None:
        rows = load_csv_rows(data_file(*self._CSV))
        entries: list[CityEntry] = []
        for row in rows:
            canonical = (row.get("canonical_name") or "").strip()
            alias = (row.get("alias") or "").strip()
            language = (row.get("language") or "").strip().lower()
            country = (row.get("country_iso") or "").strip().upper()
            kind = (row.get("kind") or "").strip().lower()
            if not canonical or not alias:
                continue
            entries.append(
                CityEntry(
                    canonical_name=canonical,
                    alias=alias,
                    language=language,
                    country_iso=country,
                    kind=kind or "city",
                )
            )
        self._entries = entries
        self._by_language: dict[str, list[CityEntry]] = {}
        for entry in entries:
            if entry.language:
                self._by_language.setdefault(entry.language, []).append(entry)

    def all_entries(self) -> list[CityEntry]:
        return list(self._entries)

    def entries_for_language(self, language_code: str | None) -> list[CityEntry]:
        code = (language_code or "").strip().lower()
        if code in self._by_language:
            return list(self._by_language[code])
        return list(self._entries)


__all__ = ["CityEntry", "EuropeanCityGazetteer"]

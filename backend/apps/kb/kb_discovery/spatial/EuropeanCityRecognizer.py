from __future__ import annotations

import re

from apps.kb.kb_discovery.common.AccentPatternBuilder import (
    accent_insensitive_fragment,
    capitalized_accent_insensitive_pattern,
)
from apps.kb.kb_discovery.gazetteers.EuropeanCityGazetteer import (
    CityEntry,
    EuropeanCityGazetteer,
)

_MIN_ALIAS_LENGTH = 3


class EuropeanCityRecognizer:
    """Európai város felismerő gazetteer alapon.

    A korábbi `LocationRecognizer` 5 hardcode-olt magyar várost ismert; ez a
    felismerő `data/cities/european_cities.csv`-t használ, így ~50 európai
    ország fővárosát + főbb városait támogatja, többnyelvű aliasokkal.

    `location_type`: "capital_city" vagy "city".
    """

    def __init__(self, gazetteer: EuropeanCityGazetteer | None = None) -> None:
        self._gazetteer = gazetteer or EuropeanCityGazetteer()
        self._patterns_by_language: dict[str, list[tuple[re.Pattern[str], CityEntry]]] = {}

    def recognize(self, text: str, language_code: str | None = None) -> list[dict]:
        patterns = self._patterns_for(language_code)
        seen: set[tuple[str, int, int]] = set()
        mentions: list[dict] = []
        for pattern, entry in patterns:
            for match in pattern.finditer(text):
                key = (entry.canonical_name.casefold(), match.start(), match.end())
                if key in seen:
                    continue
                seen.add(key)
                mentions.append(
                    {
                        "raw_text": match.group(0),
                        "normalized_location": entry.canonical_name.lower(),
                        "location_type": "capital_city" if entry.kind == "capital" else "city",
                        "start_offset": match.start(),
                        "end_offset": match.end(),
                        "metadata": {
                            "country_iso": entry.country_iso,
                            "canonical_name": entry.canonical_name,
                            "matched_alias": entry.alias,
                            "alias_language": entry.language,
                            "city_kind": entry.kind,
                        },
                    }
                )
        return mentions

    def _patterns_for(
        self, language_code: str | None
    ) -> list[tuple[re.Pattern[str], CityEntry]]:
        cache_key = (language_code or "").strip().lower() or "__all__"
        cached = self._patterns_by_language.get(cache_key)
        if cached is not None:
            return cached
        entries = self._gazetteer.entries_for_language(language_code)
        compiled: list[tuple[re.Pattern[str], CityEntry]] = []
        seen_alias: set[str] = set()
        for entry in entries:
            alias = entry.alias.strip()
            if len(alias) < _MIN_ALIAS_LENGTH:
                continue
            cache_alias = alias.casefold()
            if cache_alias in seen_alias:
                continue
            seen_alias.add(cache_alias)
            try:
                pattern = capitalized_accent_insensitive_pattern(alias)
            except re.error:
                pattern = re.compile(rf"\b{accent_insensitive_fragment(alias)}\b", re.IGNORECASE)
            compiled.append((pattern, entry))
        self._patterns_by_language[cache_key] = compiled
        return compiled


__all__ = ["EuropeanCityRecognizer"]

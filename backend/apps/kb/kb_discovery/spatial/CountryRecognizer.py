from __future__ import annotations

import re

from apps.kb.kb_discovery.common.AccentPatternBuilder import (
    accent_insensitive_fragment,
    capitalized_accent_insensitive_pattern,
)
from apps.kb.kb_discovery.gazetteers.CountryGazetteer import CountryEntry, CountryGazetteer

_MIN_ALIAS_LENGTH = 3


class CountryRecognizer:
    """Országfelismerő gazetteer alapon.

    A `data/countries/countries.csv` minden bejegyzéséhez ékezet-toleráns,
    nagybetűvel kezdődő mintát épít. Az alias 3 karakternél rövidebb sorokat
    eldobja, hogy elkerüljük a kétkarakteres ország-ISO kódok zaját.

    `location_type`: ha az ország európai, "european_country", egyébként
    "country". A normalized_location az angol kanonikus név (pl. "germany"),
    így nyelvtől függetlenül összevonhatók a találatok.
    """

    def __init__(self, gazetteer: CountryGazetteer | None = None) -> None:
        self._gazetteer = gazetteer or CountryGazetteer()
        self._patterns_by_language: dict[str, list[tuple[re.Pattern[str], CountryEntry]]] = {}

    def recognize(self, text: str, language_code: str | None = None) -> list[dict]:
        patterns = self._patterns_for(language_code)
        seen: set[tuple[str, int, int]] = set()
        mentions: list[dict] = []
        for pattern, entry in patterns:
            for match in pattern.finditer(text):
                key = (entry.iso_alpha2 or entry.canonical_name.lower(), match.start(), match.end())
                if key in seen:
                    continue
                seen.add(key)
                mentions.append(
                    {
                        "raw_text": match.group(0),
                        "normalized_location": entry.canonical_name.lower(),
                        "location_type": "european_country" if entry.is_european else "country",
                        "start_offset": match.start(),
                        "end_offset": match.end(),
                        "metadata": {
                            "iso_alpha2": entry.iso_alpha2,
                            "canonical_name": entry.canonical_name,
                            "matched_alias": entry.alias,
                            "alias_language": entry.language,
                        },
                    }
                )
        return mentions

    def _patterns_for(
        self, language_code: str | None
    ) -> list[tuple[re.Pattern[str], CountryEntry]]:
        cache_key = (language_code or "").strip().lower() or "__all__"
        cached = self._patterns_by_language.get(cache_key)
        if cached is not None:
            return cached
        entries = self._gazetteer.entries_for_language(language_code)
        compiled: list[tuple[re.Pattern[str], CountryEntry]] = []
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


__all__ = ["CountryRecognizer"]

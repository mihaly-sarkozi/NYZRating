from __future__ import annotations

import re

from apps.kb.kb_discovery.common.AccentPatternBuilder import accent_insensitive_fragment
from apps.kb.kb_discovery.gazetteers.AddressTypeGazetteer import AddressTypeGazetteer

_HU_POSTAL_CODE = r"\d{4}"
_EN_HOUSE_NUMBER = r"\d{1,5}[A-Za-z]?"
_ES_HOUSE_NUMBER = r"\d{1,5}[A-Za-z]?"
_GENERIC_HOUSE_NUMBER = r"\d{1,5}[A-Za-z]?"


class GazetteerAddressRecognizer:
    """Címfelismerő gazetteer-alapú address-type kulcsszavakkal.

    Lecseréli a régi, csak HU mintát használó `AddressRecognizer`-t. Három
    nyelvi sablont használ:

    - HU: ``<irányítószám>? <Város> <Utcanév> <utca|út|tér|krt.|...> <házszám>``
    - EN: ``<házszám> <Utcanév> <street|road|avenue|...>``
    - ES: ``<calle|avenida|paseo|...> <Utcanév> <házszám>``

    Az address-type kulcsszavakat a `data/address_types/address_types.csv` adja.
    """

    def __init__(self, gazetteer: AddressTypeGazetteer | None = None) -> None:
        self._gazetteer = gazetteer or AddressTypeGazetteer()
        self._kind_by_alias: dict[tuple[str, str], str] = {
            (entry.alias.casefold(), entry.language): entry.kind
            for entry in self._gazetteer.all_entries()
        }
        self._patterns_by_language: dict[str, list[tuple[str, re.Pattern[str]]]] = {
            "hu": self._build_hu_patterns(),
            "en": self._build_en_patterns(),
            "es": self._build_es_patterns(),
        }

    def recognize(self, text: str, language_code: str | None = None) -> list[dict]:
        code = (language_code or "").strip().lower()
        candidate_codes: list[str] = [code] if code in self._patterns_by_language else list(
            self._patterns_by_language.keys()
        )
        seen_spans: set[tuple[int, int]] = set()
        mentions: list[dict] = []
        for lang in candidate_codes:
            for kind_field, pattern in self._patterns_by_language[lang]:
                for match in pattern.finditer(text):
                    span = (match.start(), match.end())
                    if span in seen_spans:
                        continue
                    seen_spans.add(span)
                    raw_text = match.group(0).strip()
                    type_token = match.group(kind_field) if kind_field else ""
                    kind = self._kind_for(type_token, lang)
                    mentions.append(
                        {
                            "raw_text": raw_text,
                            "normalized_location": raw_text.lower(),
                            "location_type": "address",
                            "start_offset": match.start(),
                            "end_offset": match.end(),
                            "metadata": {
                                "address_kind": kind,
                                "address_language": lang,
                                "type_token": type_token,
                            },
                        }
                    )
        return mentions

    def _kind_for(self, type_token: str, language: str) -> str:
        if not type_token:
            return ""
        return self._kind_by_alias.get((type_token.casefold(), language), "")

    def _build_hu_patterns(self) -> list[tuple[str, re.Pattern[str]]]:
        type_alternation = self._alternation_for_language("hu")
        if not type_alternation:
            return []
        word = r"[A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű\.-]*"
        words = rf"{word}(?:\s+{word})*"
        type_group = rf"(?P<type>(?i:{type_alternation}))"
        with_postcode = re.compile(
            rf"\b{_HU_POSTAL_CODE}\s+{word}\s*,?\s*{words}\s+{type_group}\s*\d{{1,5}}[A-Za-z]?\.?",
            re.UNICODE,
        )
        without_postcode = re.compile(
            rf"\b{words}\s+{type_group}\s*\d{{1,5}}[A-Za-z]?\.?",
            re.UNICODE,
        )
        return [("type", with_postcode), ("type", without_postcode)]

    def _build_en_patterns(self) -> list[tuple[str, re.Pattern[str]]]:
        type_alternation = self._alternation_for_language("en")
        if not type_alternation:
            return []
        word = r"[A-Z][\w'\.-]*"
        words = rf"{word}(?:\s+{word})*"
        type_group = rf"(?P<type>(?i:{type_alternation}))"
        primary = re.compile(
            rf"\b{_EN_HOUSE_NUMBER}\s+{words}\s+{type_group}\b",
            re.UNICODE,
        )
        return [("type", primary)]

    def _build_es_patterns(self) -> list[tuple[str, re.Pattern[str]]]:
        type_alternation = self._alternation_for_language("es")
        if not type_alternation:
            return []
        word = r"[A-ZÁÉÍÓÚÜÑ][\wáéíóúüñÁÉÍÓÚÜÑ'\.-]*"
        words = rf"{word}(?:\s+(?:de|del|la|el|los|las|y|{word}))*"
        type_group = rf"(?P<type>{type_alternation})"
        primary = re.compile(
            rf"\b{type_group}\s+{words}\s*,?\s*{_ES_HOUSE_NUMBER}\b",
            re.UNICODE | re.IGNORECASE,
        )
        return [("type", primary)]

    def _alternation_for_language(self, language: str) -> str:
        aliases = sorted(
            {entry.alias for entry in self._gazetteer.entries_for_language(language)},
            key=lambda value: (-len(value), value.lower()),
        )
        if not aliases:
            return ""
        fragments = [accent_insensitive_fragment(alias) for alias in aliases]
        return "|".join(fragments)


__all__ = ["GazetteerAddressRecognizer"]

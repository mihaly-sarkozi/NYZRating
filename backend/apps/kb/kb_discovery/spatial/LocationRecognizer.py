from __future__ import annotations

import re

from apps.kb.kb_discovery.spatial.GazetteerAddressRecognizer import GazetteerAddressRecognizer


class LocationRecognizer:
    """Telephely- és iroda-felismerő (`<város>i irodában` típusú minták).

    A városlista korábban itt volt hardcode-olva; ma az
    `EuropeanCityRecognizer` látja el ezt a feladatot, így itt csak a
    `<városmelléknév>i iroda|telephely|raktár` mintákat ismerjük fel,
    amelyeket a gazetteer önmagában nem fed le.
    """

    _PATTERN = re.compile(
        r"\b(\w+?i\s+irod\w+|\w+?i\s+telephely\w+|\w+?i\s+raktár\w+)",
        re.IGNORECASE | re.UNICODE,
    )

    def recognize(self, text: str, language_code: str | None = None) -> list[dict]:
        mentions: list[dict] = []
        for match in self._PATTERN.finditer(text):
            mentions.append(
                {
                    "raw_text": match.group(1),
                    "normalized_location": match.group(1).lower(),
                    "location_type": "office",
                    "start_offset": match.start(1),
                    "end_offset": match.end(1),
                }
            )
        return mentions


class AddressRecognizer(GazetteerAddressRecognizer):
    """Visszafelé kompatibilis név a gazetteer alapú címfelismerőhöz."""


class SiteDictionaryProvider:
    def load(self, *, tenant_slug: str | None) -> list[dict]:
        return []


class RoomRecognizer:
    _PATTERN = re.compile(r"\b(tárgyaló\s[\w-]+|meeting room\s[\w-]+)\b", re.IGNORECASE)

    def recognize(self, text: str, language_code: str | None = None) -> list[dict]:
        return [
            {
                "raw_text": match.group(1),
                "normalized_location": match.group(1).lower(),
                "location_type": "room",
                "start_offset": match.start(1),
                "end_offset": match.end(1),
            }
            for match in self._PATTERN.finditer(text)
        ]


class RegionRecognizer:
    _REGIONS = ("dunántúl", "alföld", "transdanubia")

    def recognize(self, text: str, language_code: str | None = None) -> list[dict]:
        lower = text.lower()
        return [
            {"raw_text": region, "normalized_location": region, "location_type": "region"}
            for region in self._REGIONS
            if region in lower
        ]


__all__ = [
    "AddressRecognizer",
    "LocationRecognizer",
    "RegionRecognizer",
    "RoomRecognizer",
    "SiteDictionaryProvider",
]

from __future__ import annotations

import re

_HU_MONTHS = {
    "január": "01", "február": "02", "március": "03", "április": "04",
    "május": "05", "június": "06", "július": "07", "augusztus": "08",
    "szeptember": "09", "október": "10", "november": "11", "december": "12",
}

_EN_MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "sept": "09", "oct": "10",
    "nov": "11", "dec": "12",
}

_ES_MONTHS = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "setiembre": "09", "octubre": "10",
    "noviembre": "11", "diciembre": "12",
    "ene": "01", "feb": "02", "mar": "03", "abr": "04", "may": "05",
    "jun": "06", "jul": "07", "ago": "08", "sep": "09", "set": "09",
    "oct": "10", "nov": "11", "dic": "12",
}

_EN_MONTH_NAMES_PATTERN = "|".join(sorted(_EN_MONTHS.keys(), key=len, reverse=True))
_ES_MONTH_NAMES_PATTERN = "|".join(sorted(_ES_MONTHS.keys(), key=len, reverse=True))
_HU_MONTH_NAMES_PATTERN = "|".join(_HU_MONTHS.keys())


class DateRecognizer:
    """Több nyelvi dátumformátumot lefedő felismerő.

    Támogatott:
    - ISO és európai numerikus: ``2026-07-01``, ``2026.07.01``, ``2026/07/01``
    - HU szöveges: ``2026. július 1``, ``2026. július 1-től``
    - EN szöveges: ``July 1, 2026``, ``Jul 1 2026``, ``1 July 2026``
    - ES szöveges: ``1 de julio de 2026``, ``1 julio 2026``
    - DD/MM/YYYY (európai numerikus, kötőjellel/perjellel)
    """

    _NUMERIC_YMD = re.compile(r"\b(\d{4})[./-]\s?(\d{1,2})[./-]\s?(\d{1,2})\b\.?")
    _NUMERIC_DMY = re.compile(r"\b(\d{1,2})[./-]\s?(\d{1,2})[./-]\s?(\d{4})\b\.?")
    _HU = re.compile(
        rf"\b(\d{{4}})\.\s?({_HU_MONTH_NAMES_PATTERN})\s?(\d{{1,2}})(?:-től|-ig|-tól|-től)?\.?\b",
        re.IGNORECASE,
    )
    _EN_MONTH_DAY_YEAR = re.compile(
        rf"\b({_EN_MONTH_NAMES_PATTERN})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b",
        re.IGNORECASE,
    )
    _EN_DAY_MONTH_YEAR = re.compile(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_EN_MONTH_NAMES_PATTERN})\.?,?\s+(\d{{4}})\b",
        re.IGNORECASE,
    )
    _ES_DAY_MONTH_YEAR = re.compile(
        rf"\b(\d{{1,2}})(?:\s+de)?\s+({_ES_MONTH_NAMES_PATTERN})(?:\s+de)?\s+(\d{{4}})\b",
        re.IGNORECASE,
    )

    def recognize(self, chunk) -> list[dict]:
        text = chunk.text
        mentions: list[dict] = []
        seen: set[tuple[int, int]] = set()

        def _add(match, year: str, month: str, day: str, label: str) -> None:
            span = (match.start(), match.end())
            if span in seen:
                return
            try:
                normalized = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
            except ValueError:
                return
            month_int = int(month)
            day_int = int(day)
            if month_int < 1 or month_int > 12:
                return
            if day_int < 1 or day_int > 31:
                return
            seen.add(span)
            mentions.append(
                {
                    "raw_text": match.group(0),
                    "normalized_start": normalized,
                    "normalized_end": None,
                    "temporal_type": "date",
                    "start_offset": match.start(),
                    "end_offset": match.end(),
                    "metadata": {"format": label},
                }
            )

        for match in self._NUMERIC_YMD.finditer(text):
            y, m, d = match.groups()
            _add(match, y, m, d, "iso_or_dotted_ymd")

        for match in self._HU.finditer(text):
            y, month_name, d = match.groups()
            month = _HU_MONTHS[month_name.lower()]
            _add(match, y, month, d, "hu_text")

        for match in self._EN_MONTH_DAY_YEAR.finditer(text):
            month_name, d, y = match.groups()
            month = _EN_MONTHS[month_name.lower()]
            _add(match, y, month, d, "en_month_day_year")

        for match in self._EN_DAY_MONTH_YEAR.finditer(text):
            d, month_name, y = match.groups()
            month = _EN_MONTHS[month_name.lower()]
            _add(match, y, month, d, "en_day_month_year")

        for match in self._ES_DAY_MONTH_YEAR.finditer(text):
            d, month_name, y = match.groups()
            month = _ES_MONTHS[month_name.lower()]
            _add(match, y, month, d, "es_day_month_year")

        for match in self._NUMERIC_DMY.finditer(text):
            d, m, y = match.groups()
            if int(m) <= 12:
                _add(match, y, m, d, "european_dmy")

        return mentions


class DateRangeRecognizer:
    _RANGE = re.compile(
        r"\b(\d{4})[./-](\d{1,2})[./-](\d{1,2})\s*[-–]\s*(\d{4})[./-](\d{1,2})[./-](\d{1,2})\b"
    )

    def recognize(self, chunk) -> list[dict]:
        mentions: list[dict] = []
        for match in self._RANGE.finditer(chunk.text):
            y1, m1, d1, y2, m2, d2 = match.groups()
            mentions.append(
                {
                    "raw_text": match.group(0),
                    "normalized_start": f"{y1}-{int(m1):02d}-{int(d1):02d}",
                    "normalized_end": f"{y2}-{int(m2):02d}-{int(d2):02d}",
                    "temporal_type": "date_range",
                }
            )
        return mentions


class RelativeDateResolver:
    _RELATIVE = re.compile(r"\b(ma|holnap|tegnap|jövő héten|múlt héten)\b", re.IGNORECASE)

    def recognize(self, chunk) -> list[dict]:
        return [
            {
                "raw_text": match.group(0),
                "normalized_start": None,
                "normalized_end": None,
                "temporal_type": "relative",
            }
            for match in self._RELATIVE.finditer(chunk.text)
        ]


class DeadlineRecognizer:
    _DEADLINE = re.compile(r"\b(határidő|deadline)\s*:?\s*([^.!\n]+)", re.IGNORECASE)

    def recognize(self, chunk) -> list[dict]:
        return [
            {
                "raw_text": match.group(0).strip(),
                "normalized_start": None,
                "normalized_end": None,
                "temporal_type": "deadline",
            }
            for match in self._DEADLINE.finditer(chunk.text)
        ]


class RecurrenceRecognizer:
    _RECURRENCE = re.compile(r"\b(napi|heti|havi|éves|ismétlődő)\b", re.IGNORECASE)

    def recognize(self, chunk) -> list[dict]:
        return [
            {
                "raw_text": match.group(0),
                "normalized_start": None,
                "normalized_end": None,
                "temporal_type": "recurrence",
            }
            for match in self._RECURRENCE.finditer(chunk.text)
        ]


class TemporalContextScorer:
    def score(self, mention: dict) -> float:
        if mention.get("normalized_start"):
            return 0.95
        if mention.get("temporal_type") == "deadline":
            return 0.8
        return 0.6


__all__ = [
    "DateRecognizer",
    "DateRangeRecognizer",
    "DeadlineRecognizer",
    "RecurrenceRecognizer",
    "RelativeDateResolver",
    "TemporalContextScorer",
]

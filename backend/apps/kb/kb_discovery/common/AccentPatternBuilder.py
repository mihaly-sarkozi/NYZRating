from __future__ import annotations

import re
import unicodedata

_ACCENT_VARIANTS: dict[str, str] = {
    "a": "aáÁA",
    "e": "eéÉE",
    "i": "iíÍI",
    "o": "oóöőÓÖŐO",
    "u": "uúüűÚÜŰU",
}

_UPPER_ACCENT_VARIANTS: dict[str, str] = {
    "a": "ÁA",
    "e": "ÉE",
    "i": "ÍI",
    "o": "ÓÖŐO",
    "u": "ÚÜŰU",
}


def accent_insensitive_pattern(text: str) -> re.Pattern[str]:
    body = accent_insensitive_fragment(text)
    return re.compile(rf"\b{body}\b", re.IGNORECASE)


def accent_insensitive_fragment(text: str) -> str:
    parts: list[str] = []
    for char in text:
        if char.isalpha():
            base = (
                unicodedata.normalize("NFKD", char)
                .encode("ascii", "ignore")
                .decode("ascii")
                .lower()
            )
            variants = _ACCENT_VARIANTS.get(base)
            if variants:
                parts.append(f"[{variants}]")
            else:
                parts.append(re.escape(char))
        elif char.isspace():
            parts.append(r"\s+")
        else:
            parts.append(re.escape(char))
    return "".join(parts)


_AGGLUTINATIVE_SUFFIX = r"(?:[a-záéíóöőúüűA-ZÁÉÍÓÖŐÚÜŰ]{1,8})?"


def capitalized_accent_insensitive_pattern(
    text: str,
    *,
    allow_suffix: bool = True,
) -> re.Pattern[str]:
    """Ékezet-toleráns minta, ahol az első karakter KÖTELEZŐEN nagybetűs.

    Hasznos becenév- és tulajdonnév-felismerésnél, hogy a "Misi" szót csak akkor
    fogadjuk el személyként, ha a szövegben tulajdonnévi környezetben jelenik
    meg, és ne ismerjünk fel pl. "misi" kisbetűs változatot.

    `allow_suffix=True` esetén a minta opcionális toldalékot is enged a végén,
    így magyar agglutináló környezetben "Magyarországon", "Bécsben",
    "Bandival", "Misiéknek" formák is illeszkednek a "Magyarország", "Bécs",
    "Bandi", "Misi" aliasokra. Ez angol / spanyol szövegekre nem szokott
    téves találatot okozni, mert ott a tulajdonnév mellett ritkán jön
    közvetlenül szóhatár nélkül szöveg.
    """

    if not text:
        return re.compile(r"(?!x)x")
    first = text[0]
    rest = text[1:]
    parts: list[str] = []
    if first.isalpha():
        base = (
            unicodedata.normalize("NFKD", first)
            .encode("ascii", "ignore")
            .decode("ascii")
            .lower()
        )
        variants = _UPPER_ACCENT_VARIANTS.get(base)
        if variants:
            parts.append(f"[{variants}]")
        else:
            parts.append(re.escape(first.upper()))
    else:
        parts.append(re.escape(first))
    for char in rest:
        if char.isalpha():
            base = (
                unicodedata.normalize("NFKD", char)
                .encode("ascii", "ignore")
                .decode("ascii")
                .lower()
            )
            variants = _ACCENT_VARIANTS.get(base)
            if variants:
                parts.append(f"[{variants}]")
            else:
                parts.append(re.escape(char))
        elif char.isspace():
            parts.append(r"\s+")
        else:
            parts.append(re.escape(char))
    body = "".join(parts)
    suffix = _AGGLUTINATIVE_SUFFIX if allow_suffix else ""
    return re.compile(rf"\b{body}{suffix}\b")


__all__ = [
    "accent_insensitive_fragment",
    "accent_insensitive_pattern",
    "capitalized_accent_insensitive_pattern",
]

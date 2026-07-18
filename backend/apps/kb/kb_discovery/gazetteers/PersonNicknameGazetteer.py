from __future__ import annotations

from apps.kb.kb_discovery.gazetteers.data_paths import data_file
from apps.kb.kb_discovery.gazetteers.loaders import load_alias_rows


class PersonNicknameGazetteer:
    """Becenév gazetteer.

    Két szerepkört tölt be:
    - `expand_directory`: meglévő `PersonDirectoryProvider` bejegyzések alias listáját
      gazdagítja a CSV-kből.
    - `aliases_for_language` / `canonicals_for_alias`: önálló becenév-felismeréshez
      ad nyers alias listát nyelv szerint, hogy ne legyen szükség előzetes directory
      bejegyzésre. Ezt a `PersonNicknameRecognizer` használja.
    """

    _LANGUAGE_FILES: tuple[tuple[str, str], ...] = (
        ("hu", "person_aliases_hu.csv"),
        ("en", "person_aliases_en.csv"),
        ("es", "person_aliases_es.csv"),
    )

    def __init__(self) -> None:
        self._rows: list[dict[str, str]] = []
        self._rows_by_language: dict[str, list[dict[str, str]]] = {}
        for language, filename in self._LANGUAGE_FILES:
            language_rows = load_alias_rows(data_file("person_aliases", filename))
            normalized_rows = [
                {**row, "language": (row.get("language") or language).strip().lower() or language}
                for row in language_rows
            ]
            self._rows_by_language[language] = normalized_rows
            self._rows.extend(normalized_rows)

        self._aliases_by_canonical: dict[str, list[str]] = {}
        self._canonicals_by_alias: dict[str, set[str]] = {}
        self._aliases_per_language: dict[str, list[tuple[str, str]]] = {}
        for row in self._rows:
            canonical = row["canonical_name"]
            alias = row["alias"]
            language = row.get("language") or ""
            self._aliases_by_canonical.setdefault(canonical.casefold(), []).append(alias)
            self._canonicals_by_alias.setdefault(alias.casefold(), set()).add(canonical)
            if language:
                self._aliases_per_language.setdefault(language, []).append((alias, canonical))

    def expand_directory(self, directory: list[dict]) -> list[dict]:
        expanded: list[dict] = []
        for entry in directory:
            canonical = str(entry.get("name") or "").strip()
            if not canonical:
                continue
            aliases = [str(item).strip() for item in (entry.get("aliases") or []) if str(item).strip()]
            for alias in self._aliases_by_canonical.get(canonical.casefold(), []):
                if alias not in aliases:
                    aliases.append(alias)
            expanded.append({"name": canonical, "aliases": aliases})
        return expanded

    def aliases_for_language(self, language_code: str | None) -> list[tuple[str, str]]:
        """Visszaadja az adott nyelvhez tartozó (alias, canonical_name) párokat.

        Ismeretlen vagy hiányzó nyelvkód esetén az összes nyelvet vegyíti.
        """

        code = (language_code or "").strip().lower()
        if code in self._aliases_per_language:
            return list(self._aliases_per_language[code])
        merged: list[tuple[str, str]] = []
        for entries in self._aliases_per_language.values():
            merged.extend(entries)
        return merged

    def canonicals_for_alias(self, alias: str) -> set[str]:
        return set(self._canonicals_by_alias.get(alias.casefold(), set()))


__all__ = ["PersonNicknameGazetteer"]

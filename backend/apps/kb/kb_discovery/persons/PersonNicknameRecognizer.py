from __future__ import annotations

import re

from apps.kb.kb_discovery.common.AccentPatternBuilder import (
    capitalized_accent_insensitive_pattern,
)
from apps.kb.kb_discovery.common.BaseRecognizer import BaseRecognizer
from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.common.EntityCandidate import EntityCandidate
from apps.kb.kb_discovery.common.TextNormalizer import TextNormalizer
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.enums.EntityType import EntityType
from apps.kb.kb_discovery.gazetteers.PersonNicknameGazetteer import (
    PersonNicknameGazetteer,
)
from apps.kb.kb_discovery.persons.PersonConfidenceScorer import PersonConfidenceScorer

_MIN_ALIAS_LENGTH = 3


class PersonNicknameRecognizer(BaseRecognizer):
    """Becenév gazetteer alapú PERSON felismerő, directory nélkül is működik.

    Forrás: a `PersonNicknameGazetteer` által betöltött `data/person_aliases/*.csv`.
    A `PersonAliasRecognizer`-rel ellentétben ez a felismerő nem igényel előzetes
    person directory bejegyzést — a CSV-ben szereplő bárki becenevét felismeri,
    feltéve hogy a szövegben tulajdonnévi (nagybetűs) környezetben jelenik meg.

    Konfidencia kalibráció:
    - Egyértelmű alias (egyetlen kanonikus névre mutat): 0.6
    - Ambiguous alias (több kanonikus név lehetne): 0.5 (épp átengedi a min-t)
    - Ha a chunkban ott van a kanonikus teljes név is: +0.1 boost
    A directory hit confidenciája magasabb (0.9), így a `PersonCandidateFilter`
    overlap dedup logikája miatt a directory mindig nyer overlap esetén.
    """

    name = "person_nickname_gazetteer"
    version = "1.0"
    _MIN_ALIAS_LENGTH = _MIN_ALIAS_LENGTH

    def __init__(self, gazetteer: PersonNicknameGazetteer | None = None) -> None:
        self._gazetteer = gazetteer or PersonNicknameGazetteer()
        self._normalizer = TextNormalizer()
        self._scorer = PersonConfidenceScorer()
        self._compiled_cache: dict[str, list[tuple[re.Pattern[str], str, str, bool]]] = {}

    def recognize(
        self, chunks: list[DiscoveryChunkDto], context: DiscoveryContext
    ) -> list[EntityCandidate]:
        candidates: list[EntityCandidate] = []
        for chunk in chunks:
            patterns = self._patterns_for_language(chunk.language_code)
            if not patterns:
                continue
            for pattern, alias, canonical, ambiguous in patterns:
                for match in pattern.finditer(chunk.text):
                    full_name_in_chunk = self._canonical_present(chunk.text, canonical)
                    candidates.append(
                        EntityCandidate(
                            entity_type=EntityType.PERSON,
                            name=match.group(0),
                            normalized_name=self._normalizer.normalize(canonical),
                            chunk_id=chunk.chunk_id,
                            start_offset=match.start(),
                            end_offset=match.end(),
                            confidence=self._scorer.score_nickname_gazetteer(
                                ambiguous=ambiguous,
                                full_name_in_chunk=full_name_in_chunk,
                            ),
                            aliases=(alias,),
                            source=self.name,
                            language_code=chunk.language_code,
                            subtype="nickname_gazetteer",
                            metadata=(
                                ("alias", alias),
                                ("canonical_name", canonical),
                                ("ambiguous", ambiguous),
                                ("full_name_in_chunk", full_name_in_chunk),
                            ),
                        )
                    )
        return candidates

    def _patterns_for_language(
        self, language_code: str | None
    ) -> list[tuple[re.Pattern[str], str, str, bool]]:
        cache_key = (language_code or "").strip().lower() or "__all__"
        cached = self._compiled_cache.get(cache_key)
        if cached is not None:
            return cached
        rows = self._gazetteer.aliases_for_language(language_code)
        compiled: list[tuple[re.Pattern[str], str, str, bool]] = []
        seen_aliases: set[tuple[str, str]] = set()
        for alias, canonical in rows:
            alias_clean = alias.strip()
            canonical_clean = canonical.strip()
            if len(alias_clean) < self._MIN_ALIAS_LENGTH or not canonical_clean:
                continue
            key = (alias_clean.casefold(), canonical_clean.casefold())
            if key in seen_aliases:
                continue
            seen_aliases.add(key)
            canonicals = self._gazetteer.canonicals_for_alias(alias_clean)
            ambiguous = len({c.casefold() for c in canonicals}) > 1
            compiled.append(
                (
                    capitalized_accent_insensitive_pattern(alias_clean),
                    alias_clean,
                    canonical_clean,
                    ambiguous,
                )
            )
        self._compiled_cache[cache_key] = compiled
        return compiled

    @staticmethod
    def _canonical_present(text: str, canonical: str) -> bool:
        if not canonical:
            return False
        try:
            pattern = capitalized_accent_insensitive_pattern(canonical)
        except re.error:
            return False
        return pattern.search(text) is not None


__all__ = ["PersonNicknameRecognizer"]

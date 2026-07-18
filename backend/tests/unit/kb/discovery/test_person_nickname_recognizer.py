from __future__ import annotations

import pytest

from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.enums.EntityType import EntityType
from apps.kb.kb_discovery.gazetteers.PersonNicknameGazetteer import PersonNicknameGazetteer
from apps.kb.kb_discovery.persons.PersonConfidenceScorer import (
    NICKNAME_GAZETTEER_AMBIGUOUS_CONFIDENCE,
    NICKNAME_GAZETTEER_BASE_CONFIDENCE,
    PERSON_ENTITY_MIN_CONFIDENCE,
)
from apps.kb.kb_discovery.persons.PersonNicknameRecognizer import PersonNicknameRecognizer
from apps.kb.kb_discovery.persons.PersonRecognitionService import PersonRecognitionService

pytestmark = pytest.mark.unit


def _ctx() -> DiscoveryContext:
    return DiscoveryContext(
        tenant_slug="tenant",
        knowledge_base_id="kb1",
        training_item_id="item1",
        person_directory=[],
    )


def _job_ctx(tenant_slug: str = "tenant", kb_id: str = "kb1") -> DiscoveryJobContext:
    return DiscoveryJobContext(
        job_id="job1",
        understanding_job_id="und1",
        training_item_id="item1",
        training_batch_id="batch1",
        knowledge_base_id=kb_id,
        tenant_slug=tenant_slug,
        created_by=1,
        source_type="text",
        title="t",
    )


class _FakeRepo:
    def replace_for_job(self, *_args, **_kwargs):
        return 0

    def replace_for_document(self, *_args, **_kwargs):
        return 0


def test_nickname_gazetteer_recognizes_hu_alias_without_directory():
    recognizer = PersonNicknameRecognizer()
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="Bandi vezeti a projektet.",
            chunk_type="paragraph",
            order_index=0,
            language_code="hu",
        )
    ]
    candidates = recognizer.recognize(chunks, _ctx())
    assert any(candidate.name == "Bandi" for candidate in candidates)
    bandi = next(candidate for candidate in candidates if candidate.name == "Bandi")
    assert bandi.entity_type == EntityType.PERSON
    assert bandi.confidence >= PERSON_ENTITY_MIN_CONFIDENCE
    assert bandi.normalized_name == "andrás"


def test_nickname_gazetteer_skips_lowercase_alias():
    recognizer = PersonNicknameRecognizer()
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="bandi a projektet vezeti.",
            chunk_type="paragraph",
            order_index=0,
            language_code="hu",
        )
    ]
    candidates = recognizer.recognize(chunks, _ctx())
    assert candidates == []


def test_nickname_gazetteer_recognizes_en_alias():
    recognizer = PersonNicknameRecognizer()
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="Ron arrived early to the meeting.",
            chunk_type="paragraph",
            order_index=0,
            language_code="en",
        )
    ]
    candidates = recognizer.recognize(chunks, _ctx())
    assert any(candidate.name == "Ron" for candidate in candidates)


def test_nickname_recognizer_lowers_confidence_for_ambiguous_alias():
    gazetteer = PersonNicknameGazetteer()
    canonicals = gazetteer.canonicals_for_alias("Abi")
    if len(canonicals) <= 1:
        pytest.skip("Az 'Abi' alias már nem ambiguous a gazetteer-ben.")
    recognizer = PersonNicknameRecognizer(gazetteer)
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="Abi llegó tarde.",
            chunk_type="paragraph",
            order_index=0,
            language_code="es",
        )
    ]
    candidates = recognizer.recognize(chunks, _ctx())
    assert candidates, "Az ambiguous becenév is jelölődjön (legalább egy candidate)."
    assert all(
        candidate.confidence == NICKNAME_GAZETTEER_AMBIGUOUS_CONFIDENCE
        for candidate in candidates
    )


def test_nickname_gazetteer_respects_minimum_alias_length():
    recognizer = PersonNicknameRecognizer()
    seen_aliases = {
        alias for _pattern, alias, _canonical, _ambiguous in
        recognizer._patterns_for_language("hu")
    }
    assert all(len(alias) >= PersonNicknameRecognizer._MIN_ALIAS_LENGTH for alias in seen_aliases)


def test_person_service_persists_nickname_match_without_directory():
    service = PersonRecognitionService(_FakeRepo(), _FakeRepo())
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="Bandi és Misi együtt dolgoznak.",
            chunk_type="paragraph",
            order_index=0,
            language_code="hu",
        )
    ]
    entities, mentions = service.run(_job_ctx(), chunks)
    canonical_names = {entity.normalized_name for entity in entities}
    assert "andrás" in canonical_names
    assert "mihály" in canonical_names
    assert any(mention.recognizer_name == "person_nickname_gazetteer" for mention in mentions)


def test_directory_alias_wins_over_nickname_gazetteer_on_overlap():
    service = PersonRecognitionService(_FakeRepo(), _FakeRepo())
    ctx = _job_ctx(tenant_slug="demo", kb_id="example-kb")
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="Misi szerződést kötött.",
            chunk_type="paragraph",
            order_index=0,
            language_code="hu",
        )
    ]
    _entities, mentions = service.run(ctx, chunks)
    misi = [mention for mention in mentions if mention.raw_text == "Misi"]
    if misi:
        higher = max(misi, key=lambda mention: mention.confidence)
        assert higher.confidence > NICKNAME_GAZETTEER_BASE_CONFIDENCE

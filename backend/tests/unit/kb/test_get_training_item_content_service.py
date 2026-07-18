from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO

import pytest

from apps.kb.kb_ingest.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.kb_ingest.errors.TrainingNotFoundError import TrainingNotFoundError
from apps.kb.kb_ingest.service.GetTrainingItemContentService import (
    GetTrainingItemContentService,
)


@dataclass
class _FakeItem:
    id: str
    knowledge_base_id: str
    input_type: str
    raw_ref: str | None
    mime_type: str | None
    original_filename: str | None
    title: str | None


class _FakeRepository:
    def __init__(self, items: dict[str, _FakeItem]) -> None:
        self._items = items

    def get_item(self, item_id: str) -> _FakeItem | None:
        return self._items.get(item_id)


class _FakeStorage:
    def __init__(self, payloads: dict[str, bytes]) -> None:
        self._payloads = payloads

    def store_text(self, **_: object) -> str:  # pragma: no cover - not used here
        raise NotImplementedError

    def store_file(self, **_: object) -> str:  # pragma: no cover - not used here
        raise NotImplementedError

    def read_bytes(self, *, raw_ref: str) -> bytes:
        return self._payloads[raw_ref]

    def stat_bytes(self, *, raw_ref: str) -> int:  # pragma: no cover
        return len(self._payloads[raw_ref])

    def open_stream(self, *, raw_ref: str) -> BinaryIO:  # pragma: no cover
        raise NotImplementedError

    def materialize_to_temp_file(self, *, raw_ref: str) -> str:  # pragma: no cover
        raise NotImplementedError


def _make_service(items: dict[str, _FakeItem], payloads: dict[str, bytes]) -> GetTrainingItemContentService:
    return GetTrainingItemContentService(
        repository=_FakeRepository(items),
        file_storage=_FakeStorage(payloads),
    )


def test_returns_text_payload_with_default_mime() -> None:
    item = _FakeItem(
        id="training_item_1",
        knowledge_base_id="kb-1",
        input_type="text",
        raw_ref="raw/ref/1",
        mime_type=None,
        original_filename=None,
        title="Sajat cim",
    )
    service = _make_service({"training_item_1": item}, {"raw/ref/1": b"hello"})

    content = service.get_content(knowledge_base_id="kb-1", item_id="training_item_1")

    assert content.data == b"hello"
    assert content.mime_type.startswith("text/plain")
    assert "charset=utf-8" in content.mime_type.lower()
    assert content.filename.startswith("Sajat_cim")
    assert content.size_bytes == 5


def test_text_mime_without_charset_gets_utf8_charset_appended() -> None:
    item = _FakeItem(
        id="training_item_text",
        knowledge_base_id="kb-1",
        input_type="text",
        raw_ref="raw/ref/text",
        mime_type="text/plain",
        original_filename=None,
        title="ekezetes",
    )
    service = _make_service({"training_item_text": item}, {"raw/ref/text": "árvíztűrő".encode("utf-8")})

    content = service.get_content(knowledge_base_id="kb-1", item_id="training_item_text")

    assert content.mime_type == "text/plain; charset=utf-8"


def test_existing_charset_is_not_overridden() -> None:
    item = _FakeItem(
        id="training_item_iso",
        knowledge_base_id="kb-1",
        input_type="text",
        raw_ref="raw/ref/iso",
        mime_type="text/plain; charset=iso-8859-2",
        original_filename=None,
        title="latin",
    )
    service = _make_service({"training_item_iso": item}, {"raw/ref/iso": b"text"})

    content = service.get_content(knowledge_base_id="kb-1", item_id="training_item_iso")

    assert content.mime_type == "text/plain; charset=iso-8859-2"


def test_binary_mime_is_not_modified() -> None:
    item = _FakeItem(
        id="training_item_pdf",
        knowledge_base_id="kb-1",
        input_type="file",
        raw_ref="raw/ref/pdf",
        mime_type="application/pdf",
        original_filename="report.pdf",
        title="",
    )
    service = _make_service({"training_item_pdf": item}, {"raw/ref/pdf": b"%PDF-1.4"})

    content = service.get_content(knowledge_base_id="kb-1", item_id="training_item_pdf")

    assert content.mime_type == "application/pdf"


def test_uses_original_filename_for_files() -> None:
    item = _FakeItem(
        id="training_item_2",
        knowledge_base_id="kb-1",
        input_type="file",
        raw_ref="raw/ref/2",
        mime_type="application/pdf",
        original_filename="report.pdf",
        title="",
    )
    service = _make_service({"training_item_2": item}, {"raw/ref/2": b"%PDF-1.4"})

    content = service.get_content(knowledge_base_id="kb-1", item_id="training_item_2")

    assert content.filename == "report.pdf"
    assert content.mime_type == "application/pdf"


def test_typed_text_without_title_falls_back_to_default_filename() -> None:
    item = _FakeItem(
        id="training_item_3",
        knowledge_base_id="kb-1",
        input_type="text",
        raw_ref="raw/ref/3",
        mime_type="text/plain; charset=utf-8",
        original_filename=None,
        title="",
    )
    service = _make_service({"training_item_3": item}, {"raw/ref/3": b"some text"})

    content = service.get_content(knowledge_base_id="kb-1", item_id="training_item_3")

    assert content.filename.startswith("beirt-szoveg")
    assert content.filename.endswith(".txt")


def test_raises_when_item_belongs_to_other_kb() -> None:
    item = _FakeItem(
        id="training_item_4",
        knowledge_base_id="kb-OTHER",
        input_type="file",
        raw_ref="raw/ref/4",
        mime_type="application/pdf",
        original_filename="other.pdf",
        title="",
    )
    service = _make_service({"training_item_4": item}, {"raw/ref/4": b"%PDF"})

    with pytest.raises(TrainingNotFoundError) as exc:
        service.get_content(knowledge_base_id="kb-1", item_id="training_item_4")
    assert exc.value.code == TrainingErrorCode.ITEM_NOT_FOUND.value


def test_raises_when_item_missing() -> None:
    service = _make_service({}, {})

    with pytest.raises(TrainingNotFoundError):
        service.get_content(knowledge_base_id="kb-1", item_id="missing")


def test_raises_when_raw_ref_empty() -> None:
    item = _FakeItem(
        id="training_item_5",
        knowledge_base_id="kb-1",
        input_type="file",
        raw_ref=None,
        mime_type=None,
        original_filename=None,
        title="",
    )
    service = _make_service({"training_item_5": item}, {})

    with pytest.raises(TrainingNotFoundError):
        service.get_content(knowledge_base_id="kb-1", item_id="training_item_5")

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, BinaryIO

import pytest

from apps.kb.kb_ingest.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.kb_ingest.errors.TrainingNotFoundError import TrainingNotFoundError
from apps.kb.kb_ingest.service.DeleteTrainingItemService import DeleteTrainingItemService
from apps.kb.kb_ingest.service.RetrainTrainingItemService import RetrainTrainingItemService


@dataclass
class _FakeItem:
    id: str
    knowledge_base_id: str
    input_type: str = "text"
    raw_ref: str | None = "raw/ref/test"
    mime_type: str | None = "text/plain"
    original_filename: str | None = None
    title: str = ""
    content_hash: str = "hash123"
    size_bytes: int | None = 0
    metadata_json: dict | None = field(default_factory=dict)
    origin_url: str | None = None
    final_url: str | None = None
    status_code: int | None = None
    created_by: int | None = None


class _FakeRepository:
    def __init__(self, items: dict[str, _FakeItem]) -> None:
        self._items = items
        self.created_retrains: list[dict[str, Any]] = []

    def get_item(self, item_id: str) -> _FakeItem | None:
        return self._items.get(item_id)

    def create_retrain_batch_and_item(
        self,
        *,
        original: _FakeItem,
        new_batch_id: str,
        new_item_id: str,
        new_raw_ref: str,
        requested_by: int | None,
    ) -> tuple[str, str]:
        record = {
            "original_id": original.id,
            "new_batch_id": new_batch_id,
            "new_item_id": new_item_id,
            "new_raw_ref": new_raw_ref,
            "requested_by": requested_by,
        }
        self.created_retrains.append(record)
        return new_batch_id, new_item_id


@dataclass
class _FakePurgeReport:
    by_table: dict[str, int]
    soft_deleted: bool = True

    @property
    def total(self) -> int:
        return sum(self.by_table.values())


class _FakePurgeRepository:
    def __init__(self) -> None:
        self.purged: list[dict[str, Any]] = []

    def purge(
        self,
        *,
        knowledge_base_id: str,
        training_item_id: str,
        deleted_by: int | None = None,
        deleted_at_iso: str | None = None,
        reason: str | None = None,
    ) -> _FakePurgeReport:
        self.purged.append(
            {
                "knowledge_base_id": knowledge_base_id,
                "training_item_id": training_item_id,
                "deleted_by": deleted_by,
                "deleted_at_iso": deleted_at_iso,
                "reason": reason,
            }
        )
        return _FakePurgeReport(by_table={"kb_chunks": 4, "kb_ingest_items": 1})


@dataclass
class _FakeChunkDeleteResult:
    qdrant_deleted: int = 0
    failed_point_ids: tuple[str, ...] = field(default_factory=tuple)
    error_code: str | None = None

    @property
    def partial(self) -> bool:
        return bool(self.failed_point_ids) or bool(self.error_code)


class _FakeDeleteIndexedChunksService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def delete_for_training_item(self, **kwargs: Any) -> _FakeChunkDeleteResult:
        self.calls.append(kwargs)
        return _FakeChunkDeleteResult(qdrant_deleted=3)


class _FakeFileStorage:
    def __init__(self) -> None:
        self.deleted: list[str] = []
        self.stored_files: list[dict[str, Any]] = []
        self.stored_texts: list[dict[str, Any]] = []
        self.read_payload = b"sample content"

    def store_text(
        self,
        *,
        tenant: str,
        knowledge_base_id: str,
        training_batch_id: str,
        training_item_id: str,
        content: str,
        content_type: str = "text/plain",
    ) -> str:
        new_ref = f"raw/{training_batch_id}/{training_item_id}/text"
        self.stored_texts.append(
            {
                "tenant": tenant,
                "kb_id": knowledge_base_id,
                "batch": training_batch_id,
                "item": training_item_id,
                "content": content,
                "raw_ref": new_ref,
            }
        )
        return new_ref

    def store_file(
        self,
        *,
        tenant: str,
        knowledge_base_id: str,
        training_batch_id: str,
        training_item_id: str,
        data: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> str:
        new_ref = f"raw/{training_batch_id}/{training_item_id}/{filename}"
        self.stored_files.append(
            {
                "tenant": tenant,
                "kb_id": knowledge_base_id,
                "batch": training_batch_id,
                "item": training_item_id,
                "filename": filename,
                "size": len(data),
                "raw_ref": new_ref,
            }
        )
        return new_ref

    def read_bytes(self, *, raw_ref: str) -> bytes:
        return self.read_payload

    def stat_bytes(self, *, raw_ref: str) -> int:
        return len(self.read_payload)

    def open_stream(self, *, raw_ref: str) -> BinaryIO:  # pragma: no cover
        raise NotImplementedError

    def materialize_to_temp_file(self, *, raw_ref: str) -> str:  # pragma: no cover
        raise NotImplementedError

    def delete_raw(self, *, raw_ref: str) -> None:
        self.deleted.append(raw_ref)


class _FakeCollectionResolver:
    def __init__(self, name: str | None) -> None:
        self._name = name

    def get_qdrant_collection_name(self, _kb_id: str) -> str | None:
        return self._name


def _make_delete_service(
    items: dict[str, _FakeItem],
    *,
    collection: str | None = "tenant-coll",
):
    repository = _FakeRepository(items)
    purge = _FakePurgeRepository()
    file_storage = _FakeFileStorage()
    delete_chunks = _FakeDeleteIndexedChunksService()
    service = DeleteTrainingItemService(
        repository=repository,
        purge_repository=purge,
        delete_indexed_chunks_service=delete_chunks,
        file_storage=file_storage,
        knowledge_base_collection_resolver=_FakeCollectionResolver(collection),
    )
    return service, repository, purge, file_storage, delete_chunks


def test_delete_runs_purge_and_removes_raw_file() -> None:
    item = _FakeItem(id="training_item_1", knowledge_base_id="kb-1")
    service, _, purge, file_storage, delete_chunks = _make_delete_service({"training_item_1": item})

    result = service.delete(
        knowledge_base_id="kb-1",
        item_id="training_item_1",
        tenant_slug="tenant-a",
        requested_by=42,
    )

    assert result.rows_deleted == 5
    assert result.qdrant_points_deleted == 3
    assert result.qdrant_partial is False
    assert result.raw_ref_deleted is True
    assert file_storage.deleted == ["raw/ref/test"]
    assert len(purge.purged) == 1
    assert purge.purged[0]["knowledge_base_id"] == "kb-1"
    assert purge.purged[0]["training_item_id"] == "training_item_1"
    assert purge.purged[0]["deleted_by"] == 42
    assert purge.purged[0]["reason"] is None
    assert purge.purged[0]["deleted_at_iso"]
    assert len(delete_chunks.calls) == 1


def test_delete_raises_for_other_kb() -> None:
    item = _FakeItem(id="training_item_2", knowledge_base_id="kb-OTHER")
    service, *_ = _make_delete_service({"training_item_2": item})

    with pytest.raises(TrainingNotFoundError) as exc:
        service.delete(
            knowledge_base_id="kb-1",
            item_id="training_item_2",
            tenant_slug="tenant-a",
            requested_by=42,
        )
    assert exc.value.code == TrainingErrorCode.ITEM_NOT_FOUND.value


def test_retrain_creates_new_item_and_deletes_old(monkeypatch: pytest.MonkeyPatch) -> None:
    item = _FakeItem(
        id="training_item_old",
        knowledge_base_id="kb-1",
        input_type="text",
        raw_ref="raw/ref/old",
    )
    delete_service, repository, _, file_storage, _ = _make_delete_service({"training_item_old": item})

    fired: list[dict[str, Any]] = []

    def _fake_event(**kwargs: Any) -> None:
        fired.append(kwargs)

    monkeypatch.setattr(
        "apps.kb.kb_ingest.service.RetrainTrainingItemService.add_understanding_requested_event",
        _fake_event,
    )

    retrain_service = RetrainTrainingItemService(
        repository=repository,
        delete_service=delete_service,
        file_storage=file_storage,
    )

    result = retrain_service.retrain(
        knowledge_base_id="kb-1",
        item_id="training_item_old",
        tenant_slug="tenant-a",
        requested_by=99,
    )

    assert result.old_item_id == "training_item_old"
    assert result.new_item_id != "training_item_old"
    assert result.new_training_batch_id
    assert len(repository.created_retrains) == 1
    assert file_storage.stored_texts and file_storage.stored_texts[0]["item"] == result.new_item_id
    assert "raw/ref/old" in file_storage.deleted
    assert fired and fired[0]["training_item_id"] == result.new_item_id
    assert fired[0]["training_batch_id"] == result.new_training_batch_id


def test_retrain_raises_for_other_kb() -> None:
    item = _FakeItem(id="training_item_x", knowledge_base_id="kb-OTHER")
    delete_service, repository, _, file_storage, _ = _make_delete_service({"training_item_x": item})
    retrain_service = RetrainTrainingItemService(
        repository=repository,
        delete_service=delete_service,
        file_storage=file_storage,
    )

    with pytest.raises(TrainingNotFoundError):
        retrain_service.retrain(
            knowledge_base_id="kb-1",
            item_id="training_item_x",
            tenant_slug="tenant-a",
            requested_by=99,
        )

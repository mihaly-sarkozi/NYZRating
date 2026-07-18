from __future__ import annotations

# backend/apps/kb/kb_ingest/service/GetTrainingItemContentService.py
# Feladat: Egy korábban beküldött tanítási elem nyers anyagának kinyerése
# letöltéshez / új ablakos megjelenítéshez. KB-en belüli isolation: ha az
# item nem ehhez a tudástárhoz tartozik, "nem található"-ként viselkedik.
# Sárközi Mihály - 2026.06.20

from apps.kb.kb_ingest.dto.TrainingItemContent import TrainingItemContent
from apps.kb.kb_ingest.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.kb_ingest.errors.TrainingNotFoundError import TrainingNotFoundError
from apps.kb.kb_ingest.repository.TrainingRepository import TrainingRepository
from apps.kb.ports.FileStorageInterface import FileStorageInterface
from apps.kb.shared.errors import KbStorageError


_FALLBACK_MIME_BY_INPUT_TYPE: dict[str, str] = {
    "text": "text/plain; charset=utf-8",
    "url": "text/plain; charset=utf-8",
    "file": "application/octet-stream",
}

_FALLBACK_EXTENSION_BY_MIME: dict[str, str] = {
    "text/plain": "txt",
    "text/markdown": "md",
    "text/csv": "csv",
    "application/pdf": "pdf",
    "application/json": "json",
}


def _ensure_utf8_charset(mime_type: str) -> str:
    """Szöveges MIME típushoz biztosítjuk a UTF-8 charset paramétert.

    A storage rétegben ``text/plain`` formában mentjük a begépelt szöveget,
    ezért a böngésző a rendszer alapértelmezett (gyakran latin-1) kódolással
    értelmezné a választ. Az inline megnyitásnál ez ékezet-rontást okoz —
    így minden ``text/*`` típushoz hozzáfűzzük a ``charset=utf-8``-ot, ha
    még nem szerepelt benne.
    """

    primary = mime_type.split(";", 1)[0].strip().lower()
    if not primary.startswith("text/") and primary != "application/json":
        return mime_type
    if "charset=" in mime_type.lower():
        return mime_type
    separator = "; " if mime_type.strip() else ""
    return f"{mime_type.strip()}{separator}charset=utf-8"


class GetTrainingItemContentService:
    def __init__(
        self,
        *,
        repository: TrainingRepository,
        file_storage: FileStorageInterface,
    ) -> None:
        self._repository = repository
        self._file_storage = file_storage

    def get_content(
        self,
        *,
        knowledge_base_id: str,
        item_id: str,
    ) -> TrainingItemContent:
        item = self._repository.get_item(item_id)
        if item is None or item.knowledge_base_id != knowledge_base_id:
            raise TrainingNotFoundError(TrainingErrorCode.ITEM_NOT_FOUND)
        if not item.raw_ref:
            raise TrainingNotFoundError(TrainingErrorCode.ITEM_NOT_FOUND)
        try:
            data = self._file_storage.read_bytes(raw_ref=item.raw_ref)
        except KbStorageError as exc:
            raise TrainingNotFoundError(TrainingErrorCode.ITEM_NOT_FOUND) from exc

        mime_type = (item.mime_type or "").strip() or _FALLBACK_MIME_BY_INPUT_TYPE.get(
            item.input_type, "application/octet-stream"
        )
        mime_type = _ensure_utf8_charset(mime_type)
        filename = self._derive_filename(
            item_id=item.id,
            input_type=item.input_type,
            original_filename=item.original_filename,
            title=item.title,
            mime_type=mime_type,
        )
        return TrainingItemContent(
            item_id=item.id,
            knowledge_base_id=item.knowledge_base_id,
            input_type=item.input_type,
            data=data,
            mime_type=mime_type,
            filename=filename,
            size_bytes=len(data),
        )

    @staticmethod
    def _derive_filename(
        *,
        item_id: str,
        input_type: str,
        original_filename: str | None,
        title: str | None,
        mime_type: str,
    ) -> str:
        cleaned = (original_filename or "").strip()
        if cleaned:
            return cleaned
        base_title = (title or "").strip()
        if input_type == "text":
            base = base_title or "beirt-szoveg"
        elif input_type == "url":
            base = base_title or "url-input"
        else:
            base = base_title or item_id
        normalized = "_".join(base.split())
        normalized = "".join(ch for ch in normalized if ch.isalnum() or ch in "-_.")
        if not normalized:
            normalized = item_id
        if "." in normalized:
            return normalized
        primary_mime = mime_type.split(";", 1)[0].strip()
        ext = _FALLBACK_EXTENSION_BY_MIME.get(primary_mime)
        if ext:
            return f"{normalized}.{ext}"
        return normalized


__all__ = ["GetTrainingItemContentService"]

from __future__ import annotations

# backend/apps/kb/kb_ingest/router/TrainingRouter.py
# Feladat: Tanítási HTTP végpontok (szöveg batch indítás, batch részletek).
# Sárközi Mihály - 2026.06.07

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response

from apps.kb.kb_ingest.dto.FileEstimateCommand import FileEstimateCommand
from apps.kb.kb_ingest.dto.IngestRunListResponse import IngestRunListResponse
from apps.kb.kb_ingest.service.DeleteTrainingItemService import DeleteTrainingItemService
from apps.kb.kb_ingest.service.EstimateFilesService import EstimateFilesService
from apps.kb.kb_ingest.service.GetTrainingItemContentService import GetTrainingItemContentService
from apps.kb.kb_ingest.service.RetrainTrainingItemService import RetrainTrainingItemService
from apps.kb.kb_ingest.bootstrap.dependencies import (
    get_delete_training_item_service,
    get_estimate_files_service,
    get_list_ingest_runs_service,
    get_retrain_training_item_service,
    get_training_batch_service,
    get_training_file_service,
    get_training_item_content_service,
    get_training_text_service,
    require_kb_read,
    require_kb_train,
)
from apps.kb.kb_ingest.bootstrap.service_keys import KB_INGEST_REPOSITORY
from core.kernel.http.app_dependencies import get_module_repository
from apps.kb.kb_ingest.dto.TrainingBatchStatusResponse import TrainingBatchStatusResponse
from apps.kb.kb_ingest.dto.TrainingFileEstimateResponse import TrainingFileEstimateResponse
from apps.kb.kb_ingest.dto.TrainingTextResponse import TrainingTextResponse
from apps.kb.kb_ingest.mapper.training_file_estimate_mapper import to_training_file_estimate
from apps.kb.kb_ingest.mapper.training_response_mapper import to_text_response, to_text_response_from_batch_status
from apps.kb.kb_ingest.dto.TrainingTextRequest import TrainingTextRequest
from apps.kb.kb_ingest.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.kb_ingest.errors.TrainingDuplicateError import TrainingDuplicateError
from apps.kb.kb_ingest.errors.TrainingNotFoundError import TrainingNotFoundError
from apps.kb.kb_ingest.errors.TrainingProcessingError import TrainingProcessingError
from apps.kb.kb_ingest.errors.TrainingQueueUnavailableError import TrainingQueueUnavailableError
from apps.kb.kb_ingest.errors.TrainingQuotaExceededError import TrainingQuotaExceededError
from apps.kb.kb_ingest.service.ListIngestRunsService import ListIngestRunsService
from apps.kb.kb_ingest.service.TrainingBatchService import TrainingBatchService
from apps.kb.kb_ingest.service.TrainingFileService import TrainingFileService
from apps.kb.kb_ingest.service.TrainingTextService import TrainingTextService
from apps.kb.kb_ingest.validation.TrainingValidationError import TrainingValidationError
from apps.kb.shared.errors import KbNotFoundError, KbValidationError
from shared.utils.tenant_slug import tenant_slug_or_default
from core.kernel.http.tenant_dependencies import require_tenant_context
from core.modules.tenant.context.request_tenant_context import RequestTenantContext
from core.modules.users.domain.dto import User

router = APIRouter()


def _coded_error_detail(exc: object, *, fallback_code: str) -> dict[str, object]:
    code = str(getattr(exc, "code", fallback_code) or fallback_code)
    detail: dict[str, object] = {"code": code}
    params = getattr(exc, "params", None)
    if params:
        detail["params"] = params
    return detail


def _raise_training_validation_http(exc: TrainingValidationError) -> None:
    if exc.code == TrainingErrorCode.KNOWLEDGE_BASE_NOT_FOUND.value:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.KNOWLEDGE_BASE_NOT_FOUND.value),
        )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.VALIDATION_ERROR.value),
    )


def _raise_training_quota_http(exc: TrainingQuotaExceededError) -> None:
    detail = _coded_error_detail(exc, fallback_code=TrainingErrorCode.QUOTA_EXCEEDED.value)
    detail["required_chars"] = exc.required_chars
    detail["remaining_chars"] = exc.remaining_chars
    detail["available_chars"] = exc.available_chars
    detail["trained_chars"] = exc.trained_chars
    detail["included_chars"] = exc.included_chars
    detail["plan_code"] = exc.plan_code
    detail["plan_name"] = exc.plan_name
    detail["is_highest_tier"] = exc.is_highest_tier
    detail["next_plan_code"] = exc.next_plan_code
    detail["next_plan_name"] = exc.next_plan_name
    detail["next_plan_included_chars"] = exc.next_plan_included_chars
    detail["message"] = exc.message_text
    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail=detail,
    )


@router.post("/{kb_id}/training/text", response_model=TrainingTextResponse)
async def create_text_training_batch(
    kb_id: str,
    body: TrainingTextRequest,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    training_service: TrainingTextService = Depends(get_training_text_service),
    current_user: User = Depends(require_kb_train),
) -> TrainingTextResponse:
    try:
        result = await training_service.submit_text_training(
            tenant=tenant_slug_or_default(tenant),
            knowledge_base_id=kb_id,
            created_by=current_user.id,
            request=body,
            usage_tenant=tenant,
        )
        return to_text_response(
            batch_id=result.training_batch_id,
            status=result.status,
            created_at=result.created_at,
            completed_at=result.completed_at,
        )
    except TrainingDuplicateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.DUPLICATE_CONTENT.value),
        ) from exc
    except TrainingValidationError as exc:
        _raise_training_validation_http(exc)
    except TrainingQuotaExceededError as exc:
        _raise_training_quota_http(exc)
    except TrainingQueueUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.QUEUE_UNAVAILABLE.value),
        ) from exc
    except TrainingProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.INTERNAL_ERROR.value),
        ) from exc
    except KbValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.VALIDATION_ERROR.value),
        ) from exc


@router.post("/{kb_id}/training/files/estimate", response_model=TrainingFileEstimateResponse)
async def estimate_file_training(
    kb_id: str,
    request: Request,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    estimate_service: EstimateFilesService = Depends(get_estimate_files_service),
    files: list[UploadFile] = File(...),
    _: User = Depends(require_kb_train),
) -> TrainingFileEstimateResponse:
    repository = get_module_repository(KB_INGEST_REPOSITORY, request)
    try:
        repository.ensure_active_knowledge_base(kb_id)
    except TrainingValidationError as exc:
        _raise_training_validation_http(exc)
    result = await estimate_service.execute(FileEstimateCommand(tenant=tenant, uploads=files))
    return to_training_file_estimate(result)


@router.post("/{kb_id}/training/files", response_model=TrainingTextResponse)
async def create_file_training_batch(
    kb_id: str,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    file_service: TrainingFileService = Depends(get_training_file_service),
    batch_service: TrainingBatchService = Depends(get_training_batch_service),
    files: list[UploadFile] = File(...),
    current_user: User = Depends(require_kb_train),
) -> TrainingTextResponse:
    try:
        result = await file_service.submit_file_training(
            tenant=tenant_slug_or_default(tenant),
            knowledge_base_id=kb_id,
            created_by=current_user.id,
            uploads=files,
            usage_tenant=tenant,
        )
        return to_text_response_from_batch_status(
            batch_service.get_status(result.training_batch_id, tenant=tenant_slug_or_default(tenant))
        )
    except TrainingDuplicateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.DUPLICATE_CONTENT.value),
        ) from exc
    except TrainingValidationError as exc:
        _raise_training_validation_http(exc)
    except TrainingQuotaExceededError as exc:
        _raise_training_quota_http(exc)
    except TrainingQueueUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.QUEUE_UNAVAILABLE.value),
        ) from exc
    except TrainingProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.INTERNAL_ERROR.value),
        ) from exc
    except KbValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.VALIDATION_ERROR.value),
        ) from exc


@router.get("/{kb_id}/ingest/runs", response_model=IngestRunListResponse)
def list_ingest_runs(
    kb_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    tenant: RequestTenantContext = Depends(require_tenant_context),
    list_service: ListIngestRunsService = Depends(get_list_ingest_runs_service),
    _: User = Depends(require_kb_read),
) -> IngestRunListResponse:
    return list_service.list_runs(kb_id, limit=limit, offset=offset)


@router.get("/{kb_id}/training/items/{item_id}/raw")
def download_training_item_raw(
    kb_id: str,
    item_id: str,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    content_service: GetTrainingItemContentService = Depends(get_training_item_content_service),
    _: User = Depends(require_kb_read),
) -> Response:
    try:
        content = content_service.get_content(
            knowledge_base_id=kb_id,
            item_id=item_id,
        )
    except TrainingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.ITEM_NOT_FOUND.value),
        ) from exc

    safe_filename = content.filename.replace('"', "")
    headers = {
        "Content-Disposition": f'inline; filename="{safe_filename}"',
        "Content-Length": str(content.size_bytes),
        "Cache-Control": "private, no-store",
    }
    return Response(
        content=content.data,
        media_type=content.mime_type,
        headers=headers,
    )


@router.delete("/{kb_id}/training/items/{item_id}")
def delete_training_item(
    kb_id: str,
    item_id: str,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    delete_service: DeleteTrainingItemService = Depends(get_delete_training_item_service),
    current_user: User = Depends(require_kb_train),
) -> dict[str, object]:
    try:
        result = delete_service.delete(
            knowledge_base_id=kb_id,
            item_id=item_id,
            tenant_slug=tenant_slug_or_default(tenant),
            requested_by=current_user.id,
        )
    except TrainingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.ITEM_NOT_FOUND.value),
        ) from exc

    return {
        "item_id": result.item_id,
        "knowledge_base_id": result.knowledge_base_id,
        "qdrant_points_deleted": result.qdrant_points_deleted,
        "qdrant_partial": result.qdrant_partial,
        "rows_deleted": result.rows_deleted,
        "rows_by_table": result.rows_by_table,
        "raw_ref_deleted": result.raw_ref_deleted,
    }


@router.get("/{kb_id}/training/items/{item_id}/retrain/preview")
def preview_retrain_training_item(
    kb_id: str,
    item_id: str,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    retrain_service: RetrainTrainingItemService = Depends(get_retrain_training_item_service),
    _: User = Depends(require_kb_train),
) -> dict[str, object]:
    try:
        preview = retrain_service.preview(
            knowledge_base_id=kb_id,
            item_id=item_id,
            usage_tenant=tenant,
        )
    except TrainingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.ITEM_NOT_FOUND.value),
        ) from exc

    return {
        "knowledge_base_id": preview.knowledge_base_id,
        "item_id": preview.item_id,
        "required_chars": preview.required_chars,
        "remaining_chars": preview.remaining_chars,
        "available_chars": preview.available_chars,
        "would_exceed": preview.would_exceed,
        "can_retrain": preview.can_retrain,
    }


@router.post("/{kb_id}/training/items/{item_id}/retrain")
def retrain_training_item(
    kb_id: str,
    item_id: str,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    retrain_service: RetrainTrainingItemService = Depends(get_retrain_training_item_service),
    current_user: User = Depends(require_kb_train),
) -> dict[str, object]:
    try:
        result = retrain_service.retrain(
            knowledge_base_id=kb_id,
            item_id=item_id,
            tenant_slug=tenant_slug_or_default(tenant),
            requested_by=current_user.id,
            usage_tenant=tenant,
        )
    except TrainingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.ITEM_NOT_FOUND.value),
        ) from exc
    except TrainingQuotaExceededError as exc:
        _raise_training_quota_http(exc)
    except TrainingProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.INTERNAL_ERROR.value),
        ) from exc
    except TrainingQueueUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.QUEUE_UNAVAILABLE.value),
        ) from exc

    return {
        "knowledge_base_id": result.knowledge_base_id,
        "old_item_id": result.old_item_id,
        "new_item_id": result.new_item_id,
        "new_training_batch_id": result.new_training_batch_id,
        "qdrant_points_deleted": result.qdrant_points_deleted,
        "rows_deleted": result.rows_deleted,
    }


@router.get("/training/batches/{batch_id}", response_model=TrainingBatchStatusResponse)
def get_training_batch(
    batch_id: str,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    batch_service: TrainingBatchService = Depends(get_training_batch_service),
    _: User = Depends(require_kb_train),
) -> TrainingBatchStatusResponse:
    try:
        return batch_service.get_status(batch_id, tenant=tenant_slug_or_default(tenant))
    except TrainingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.BATCH_NOT_FOUND.value),
        ) from exc
    except KbNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.BATCH_NOT_FOUND.value),
        ) from exc


__all__ = ["router"]

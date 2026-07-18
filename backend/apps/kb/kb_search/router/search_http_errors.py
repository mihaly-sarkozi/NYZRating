from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from apps.kb.kb_search.enums.SearchErrorCode import SearchErrorCode
from apps.kb.kb_search.errors.SearchNotReadyError import SearchNotReadyError
from apps.kb.kb_search.errors.SearchQdrantFailedError import SearchQdrantFailedError
from apps.kb.kb_search.errors.SearchQueryEmbeddingFailedError import SearchQueryEmbeddingFailedError


_CODE_STATUS: dict[SearchErrorCode, int] = {
    SearchErrorCode.KB_NOT_READY: 423,
    SearchErrorCode.PERMISSION_DENIED: 403,
    SearchErrorCode.TENANT_SCOPE_MISMATCH: 403,
    SearchErrorCode.KB_NOT_FOUND: 404,
    SearchErrorCode.QDRANT_FAILED: 503,
    SearchErrorCode.QUERY_EMBEDDING_FAILED: 503,
    SearchErrorCode.QUERY_EMBEDDING_DIMENSION_MISMATCH: 500,
    SearchErrorCode.CITATION_BUILD_FAILED: 500,
}


def _http_error(code: SearchErrorCode, message: str, **extra: Any) -> HTTPException:
    detail: dict[str, Any] = {"code": code.value, "message": message}
    detail.update(extra)
    return HTTPException(status_code=_CODE_STATUS.get(code, 500), detail=detail)


def raise_if_blocked_search_result(result: dict[str, Any]) -> None:
    answer_mode = str(result.get("answer_mode") or "").strip().upper()
    if answer_mode != "BLOCKED_NOT_READY":
        return
    readiness = dict(result.get("readiness") or {})
    raise _http_error(
        SearchErrorCode.KB_NOT_READY,
        str(result.get("error_message") or "A kiválasztott tudástár még nem kereshető."),
        blocked_reasons=list(readiness.get("blocking_issues") or readiness.get("blocked_reasons") or []),
        readiness=readiness,
        query_run_id=result.get("query_run_id"),
    )


def map_search_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, SearchNotReadyError):
        return _http_error(
            SearchErrorCode.KB_NOT_READY,
            exc.message,
            blocked_reasons=list(exc.blocked_reasons),
        )
    if isinstance(exc, PermissionError):
        return _http_error(SearchErrorCode.PERMISSION_DENIED, str(exc))
    if isinstance(exc, SearchQdrantFailedError):
        return _http_error(SearchErrorCode.QDRANT_FAILED, exc.message)
    if isinstance(exc, SearchQueryEmbeddingFailedError):
        return _http_error(SearchErrorCode.QUERY_EMBEDDING_FAILED, exc.message)

    message = str(exc)
    for code in SearchErrorCode:
        if code.value in message and code in _CODE_STATUS:
            return _http_error(code, message)
    return HTTPException(status_code=500, detail={"code": "SEARCH_INTERNAL_ERROR", "message": message})


__all__ = ["map_search_exception", "raise_if_blocked_search_result"]

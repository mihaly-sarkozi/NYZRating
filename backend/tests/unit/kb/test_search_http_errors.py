from __future__ import annotations

import pytest
from fastapi import HTTPException

from apps.kb.kb_search.enums.SearchErrorCode import SearchErrorCode
from apps.kb.kb_search.errors.SearchNotReadyError import SearchNotReadyError
from apps.kb.kb_search.errors.SearchQdrantFailedError import SearchQdrantFailedError
from apps.kb.kb_search.errors.SearchQueryEmbeddingFailedError import SearchQueryEmbeddingFailedError
from apps.kb.kb_search.router.search_http_errors import map_search_exception, raise_if_blocked_search_result

pytestmark = pytest.mark.unit


def test_raise_if_blocked_search_result_maps_not_ready_to_423() -> None:
    with pytest.raises(HTTPException) as exc:
        raise_if_blocked_search_result(
            {
                "answer_mode": "BLOCKED_NOT_READY",
                "error_message": "Index nincs kész",
                "readiness": {"blocking_issues": ["qdrant_not_verified"]},
                "query_run_id": "qry_1",
            }
        )
    assert exc.value.status_code == 423
    assert exc.value.detail["code"] == SearchErrorCode.KB_NOT_READY.value


def test_map_search_exception_not_ready() -> None:
    exc = map_search_exception(SearchNotReadyError(blocked_reasons=("missing_index",)))
    assert exc.status_code == 423
    assert exc.detail["code"] == SearchErrorCode.KB_NOT_READY.value


def test_map_search_exception_permission() -> None:
    exc = map_search_exception(PermissionError("denied"))
    assert exc.status_code == 403
    assert exc.detail["code"] == SearchErrorCode.PERMISSION_DENIED.value


def test_map_search_exception_qdrant() -> None:
    exc = map_search_exception(SearchQdrantFailedError("timeout"))
    assert exc.status_code == 503
    assert exc.detail["code"] == SearchErrorCode.QDRANT_FAILED.value


def test_map_search_exception_embedding() -> None:
    exc = map_search_exception(SearchQueryEmbeddingFailedError("model unavailable"))
    assert exc.status_code == 503
    assert exc.detail["code"] == SearchErrorCode.QUERY_EMBEDDING_FAILED.value


def test_map_search_exception_unknown() -> None:
    exc = map_search_exception(RuntimeError("unexpected"))
    assert exc.status_code == 500
    assert exc.detail["code"] == "SEARCH_INTERNAL_ERROR"

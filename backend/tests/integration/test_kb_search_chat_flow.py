from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from apps.chat.service.answer_source_builder import AnswerSourceBuilder

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("allow_chat_usage")]


def _search_packet(*, answer_mode: str = "ANSWERED") -> dict:
    citations = [
        {
            "citation_id": "CIT-1",
            "source_id": "chunk-abc",
            "document_title": "HR kézikönyv",
            "page_numbers": [12, 13],
            "section_title": "Szabadság",
            "snippet": "Évente 20 nap szabadság jár.",
            "kb_uuid": "kb-1",
            "download_ref": "source:chunk-abc",
            "download_url": "/api/chat/sources/qry_1/chunk-abc/download",
            "download_url_template": "/api/chat/sources/{query_run_id}/{source_id}/download",
        }
    ]
    return {
        "query_run_id": "qry_1",
        "answer_mode": answer_mode,
        "kb_uuid": "kb-1",
        "sources": citations,
        "citation_records": citations,
        "citations": ["CIT-1"],
        "context_blocks": [{"source_id": "chunk-abc", "snippet": "Évente 20 nap szabadság jár."}],
        "readiness": {"ready_for_search": True, "qdrant_verified": True},
    }


def test_kb_search_router_returns_citation_metadata(client_authenticated: TestClient, app) -> None:
    from apps.kb.kb_search.bootstrap.dependencies import get_kb_search_pipeline

    pipeline = MagicMock()
    pipeline.execute.return_value = _search_packet()
    app.dependency_overrides[get_kb_search_pipeline] = lambda: pipeline
    try:
        response = client_authenticated.post(
            "/api/kb/search",
            json={"question": "Mennyi szabadság jár?", "kb_uuid": "kb-1"},
        )
        assert response.status_code == 200
        body = response.json()
        source = body["sources"][0]
        assert source["citation_id"] == "CIT-1"
        assert source["download_url"].endswith("/chunk-abc/download")
        assert source["download_url_template"]
        assert source["download_ref"] == "source:chunk-abc"
        assert source["page_numbers"] == [12, 13]
        assert source["section_title"] == "Szabadság"
        assert body["citation_records"][0]["citation_id"] == "CIT-1"
    finally:
        app.dependency_overrides.pop(get_kb_search_pipeline, None)


def test_kb_search_router_maps_not_ready_to_423(client_authenticated: TestClient, app) -> None:
    from apps.kb.kb_search.bootstrap.dependencies import get_kb_search_pipeline

    pipeline = MagicMock()
    pipeline.execute.return_value = {
        **_search_packet(answer_mode="BLOCKED_NOT_READY"),
        "error_message": "Qdrant még nincs ellenőrizve",
        "readiness": {"blocking_issues": ["qdrant_not_verified"]},
    }
    app.dependency_overrides[get_kb_search_pipeline] = lambda: pipeline
    try:
        response = client_authenticated.post(
            "/api/kb/search",
            json={"question": "Teszt?", "kb_uuid": "kb-1"},
        )
        assert response.status_code == 423
        assert response.json()["detail"]["code"] == "SEARCH_KB_NOT_READY"
    finally:
        app.dependency_overrides.pop(get_kb_search_pipeline, None)


def test_kb_search_router_maps_qdrant_failure_to_503(client_authenticated: TestClient, app) -> None:
    from apps.kb.kb_search.bootstrap.dependencies import get_kb_search_pipeline
    from apps.kb.kb_search.errors.SearchQdrantFailedError import SearchQdrantFailedError

    pipeline = MagicMock()
    pipeline.execute.side_effect = SearchQdrantFailedError("connection refused")
    app.dependency_overrides[get_kb_search_pipeline] = lambda: pipeline
    try:
        response = client_authenticated.post(
            "/api/kb/search",
            json={"question": "Teszt?", "kb_uuid": "kb-1"},
        )
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "SEARCH_QDRANT_FAILED"
    finally:
        app.dependency_overrides.pop(get_kb_search_pipeline, None)


def test_chat_response_preserves_citation_metadata_from_kb_packet(
    client_authenticated: TestClient,
    mock_chat_service,
    app,
) -> None:
    from apps.chat.bootstrap.dependencies import get_chat_service

    packet = _search_packet()
    builder = AnswerSourceBuilder(sanitize_debug_text=lambda value: str(value or ""))
    sources = builder.build_sources_from_packet(packet)
    mock_chat_service.chat_with_sources = AsyncMock(
        return_value={
            "answer": "Évente 20 nap szabadság jár.",
            "query_run_id": packet["query_run_id"],
            "answer_mode": "answered",
            "answer_source": "knowledge",
            "confidence": 0.91,
            "sources": sources,
            "citation_records": packet["citation_records"],
            "citations": packet["citations"],
            "evidence": [],
            "cited_claim_ids": [],
            "cited_sentence_ids": [],
            "cited_source_ids": ["chunk-abc"],
            "query_profile": {},
            "matched_chunks": [],
            "claims": [],
            "context_blocks": packet["context_blocks"],
        }
    )
    app.dependency_overrides[get_chat_service] = lambda: mock_chat_service
    try:
        response = client_authenticated.post(
            "/api/chat",
            json={"question": "Mennyi szabadság jár?", "kb_uuid": "kb-1"},
        )
        assert response.status_code == 200
        source = response.json()["sources"][0]
        assert source["citation_id"] == "CIT-1"
        assert source["download_url"]
        assert source["page_numbers"] == [12, 13]
        assert response.json()["citation_records"][0]["section_title"] == "Szabadság"
    finally:
        app.dependency_overrides.pop(get_chat_service, None)

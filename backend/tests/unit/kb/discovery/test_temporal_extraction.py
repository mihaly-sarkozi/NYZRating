from __future__ import annotations

import pytest

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.temporal.DateRecognizer import DateRecognizer

pytestmark = pytest.mark.unit


def _chunk(text: str) -> DiscoveryChunkDto:
    return DiscoveryChunkDto(chunk_id="c1", text=text, chunk_type="paragraph", order_index=0)


def test_hungarian_date_extraction():
    recognizer = DateRecognizer()
    mentions = recognizer.recognize(_chunk("2026. július 1-től érvényes."))
    assert len(mentions) == 1
    assert mentions[0]["normalized_start"] == "2026-07-01"


def test_iso_date_extraction():
    recognizer = DateRecognizer()
    mentions = recognizer.recognize(_chunk("Effective from 2026-07-15."))
    starts = {mention["normalized_start"] for mention in mentions}
    assert "2026-07-15" in starts


def test_english_month_day_year_extraction():
    recognizer = DateRecognizer()
    mentions = recognizer.recognize(_chunk("The contract starts on July 15, 2026."))
    starts = {mention["normalized_start"] for mention in mentions}
    assert "2026-07-15" in starts


def test_english_day_month_year_extraction():
    recognizer = DateRecognizer()
    mentions = recognizer.recognize(_chunk("The deadline is 15 July 2026 sharp."))
    starts = {mention["normalized_start"] for mention in mentions}
    assert "2026-07-15" in starts


def test_english_short_month_extraction():
    recognizer = DateRecognizer()
    mentions = recognizer.recognize(_chunk("Released Jan 5, 2026 to clients."))
    starts = {mention["normalized_start"] for mention in mentions}
    assert "2026-01-05" in starts


def test_spanish_date_extraction():
    recognizer = DateRecognizer()
    mentions = recognizer.recognize(_chunk("La reunión es el 15 de julio de 2026."))
    starts = {mention["normalized_start"] for mention in mentions}
    assert "2026-07-15" in starts


def test_european_dmy_numeric_extraction():
    recognizer = DateRecognizer()
    mentions = recognizer.recognize(_chunk("Megrendelés ideje: 15.07.2026."))
    starts = {mention["normalized_start"] for mention in mentions}
    assert "2026-07-15" in starts


def test_invalid_month_in_dmy_skipped():
    recognizer = DateRecognizer()
    mentions = recognizer.recognize(_chunk("Verzió: 1.20.2026"))
    starts = {mention["normalized_start"] for mention in mentions}
    assert "2026-20-01" not in starts

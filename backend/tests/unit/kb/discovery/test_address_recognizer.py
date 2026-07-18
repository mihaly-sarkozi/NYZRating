from __future__ import annotations

import pytest

from apps.kb.kb_discovery.gazetteers.AddressTypeGazetteer import AddressTypeGazetteer
from apps.kb.kb_discovery.spatial.GazetteerAddressRecognizer import GazetteerAddressRecognizer

pytestmark = pytest.mark.unit


def test_address_recognizer_finds_hungarian_address():
    recognizer = GazetteerAddressRecognizer()
    mentions = recognizer.recognize(
        "Az iroda címe: 1051 Budapest, Petőfi Sándor utca 12.", "hu"
    )
    assert any("Petőfi" in mention["raw_text"] for mention in mentions)
    assert all(mention["location_type"] == "address" for mention in mentions)


def test_address_recognizer_finds_english_address():
    recognizer = GazetteerAddressRecognizer()
    mentions = recognizer.recognize(
        "The shop is at 221 Baker Street in London.", "en"
    )
    raw_texts = [mention["raw_text"] for mention in mentions]
    assert any("Baker Street" in text for text in raw_texts)


def test_address_recognizer_finds_spanish_address():
    recognizer = GazetteerAddressRecognizer()
    mentions = recognizer.recognize(
        "Vive en Calle Mayor 12, 28001 Madrid.", "es"
    )
    assert any("Calle Mayor" in mention["raw_text"] for mention in mentions)


def test_address_recognizer_categorizes_kind():
    recognizer = GazetteerAddressRecognizer()
    mentions = recognizer.recognize(
        "Az iroda címe: 1051 Budapest, Andrássy út 12.", "hu"
    )
    assert any(mention["metadata"]["address_kind"] == "road" for mention in mentions)


def test_address_type_gazetteer_loads_three_languages():
    gazetteer = AddressTypeGazetteer()
    languages = {entry.language for entry in gazetteer.all_entries()}
    assert {"hu", "en", "es"}.issubset(languages)

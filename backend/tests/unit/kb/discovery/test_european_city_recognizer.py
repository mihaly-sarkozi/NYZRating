from __future__ import annotations

import pytest

from apps.kb.kb_discovery.gazetteers.EuropeanCityGazetteer import EuropeanCityGazetteer
from apps.kb.kb_discovery.spatial.EuropeanCityRecognizer import EuropeanCityRecognizer

pytestmark = pytest.mark.unit


def test_european_city_recognizer_finds_capital_in_hungarian_text():
    recognizer = EuropeanCityRecognizer()
    mentions = recognizer.recognize("A találkozó Bécsben lesz, majd Berlinbe utazunk.", "hu")
    canonicals = {mention["metadata"]["canonical_name"] for mention in mentions}
    assert "Vienna" in canonicals
    assert "Berlin" in canonicals
    types = {mention["metadata"]["canonical_name"]: mention["location_type"] for mention in mentions}
    assert types["Vienna"] == "capital_city"


def test_european_city_recognizer_finds_paris_in_spanish_text():
    recognizer = EuropeanCityRecognizer()
    mentions = recognizer.recognize("La conferencia se celebra en París este año.", "es")
    canonicals = {mention["metadata"]["canonical_name"] for mention in mentions}
    assert "Paris" in canonicals


def test_european_city_recognizer_finds_hungarian_major_city():
    recognizer = EuropeanCityRecognizer()
    mentions = recognizer.recognize("A debreceni iroda Debrecenben található.", "hu")
    canonicals = {mention["metadata"]["canonical_name"] for mention in mentions}
    assert "Debrecen" in canonicals


def test_european_city_gazetteer_includes_major_european_capitals():
    gazetteer = EuropeanCityGazetteer()
    by_country = {entry.country_iso for entry in gazetteer.all_entries() if entry.kind == "capital"}
    assert {"HU", "DE", "FR", "ES", "IT", "AT", "GB"}.issubset(by_country)

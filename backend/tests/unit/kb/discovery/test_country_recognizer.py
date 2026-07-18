from __future__ import annotations

import pytest

from apps.kb.kb_discovery.gazetteers.CountryGazetteer import CountryGazetteer
from apps.kb.kb_discovery.spatial.CountryRecognizer import CountryRecognizer

pytestmark = pytest.mark.unit


def test_country_recognizer_finds_hungarian_country_in_hungarian_text():
    recognizer = CountryRecognizer()
    mentions = recognizer.recognize("A cég Magyarországon és Németországban működik.", "hu")
    iso_codes = {mention["metadata"]["iso_alpha2"] for mention in mentions}
    assert "HU" in iso_codes
    assert "DE" in iso_codes


def test_country_recognizer_finds_english_country_in_english_text():
    recognizer = CountryRecognizer()
    mentions = recognizer.recognize("The office is located in Germany and Italy.", "en")
    iso_codes = {mention["metadata"]["iso_alpha2"] for mention in mentions}
    assert {"DE", "IT"}.issubset(iso_codes)


def test_country_recognizer_marks_european_flag():
    recognizer = CountryRecognizer()
    mentions = recognizer.recognize("Spain and Brazil are partner countries.", "en")
    types = {mention["metadata"]["iso_alpha2"]: mention["location_type"] for mention in mentions}
    assert types.get("ES") == "european_country"
    assert types.get("BR") == "country"


def test_country_recognizer_skips_short_aliases():
    recognizer = CountryRecognizer()
    mentions = recognizer.recognize("Talked about HU vs DE.", "en")
    iso_codes = {mention["metadata"]["iso_alpha2"] for mention in mentions}
    assert "HU" not in iso_codes
    assert "DE" not in iso_codes


def test_country_gazetteer_loads_european_countries():
    gazetteer = CountryGazetteer()
    european = {entry.iso_alpha2 for entry in gazetteer.all_entries() if entry.is_european}
    assert {"HU", "DE", "FR", "ES", "IT", "GB", "AT", "PL", "RO"}.issubset(european)

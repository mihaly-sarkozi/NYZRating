from __future__ import annotations

_SCORE_BY_LOCATION_TYPE: dict[str, float] = {
    "office": 0.9,
    "address": 0.9,
    "capital_city": 0.88,
    "european_country": 0.85,
    "country": 0.85,
    "city": 0.82,
    "region": 0.78,
    "room": 0.75,
}


class SpatialContextScorer:
    def score(self, mention: dict) -> float:
        location_type = (mention.get("location_type") or "").strip().lower()
        return _SCORE_BY_LOCATION_TYPE.get(location_type, 0.75)


__all__ = ["SpatialContextScorer"]

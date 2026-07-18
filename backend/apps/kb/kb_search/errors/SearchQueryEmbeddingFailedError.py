from __future__ import annotations


class SearchQueryEmbeddingFailedError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


__all__ = ["SearchQueryEmbeddingFailedError"]

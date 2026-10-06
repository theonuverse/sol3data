"""Uniform named collection models."""
from collections.abc import Iterator
from typing import Generic, TypeVar

from ._errors import CollectionItemNotFoundError
from ._normalization import normalize_key

T = TypeVar("T")


class NamedCollection(Generic[T]):
    """A case-insensitive named collection with strict and optional lookup."""

    def __init__(self, values: dict[str, T], *, label: str = "Item") -> None:
        self._values = dict(values)
        self._label = label

    def get(self, name: str) -> T:
        for actual, value in self._values.items():
            if normalize_key(actual) == normalize_key(name):
                return value
        available = ", ".join(self._values) or "none"
        raise CollectionItemNotFoundError(
            f"{self._label} '{name}' does not exist. Available: {available}."
        )

    def find(self, name: str) -> T | None:
        try:
            return self.get(name)
        except CollectionItemNotFoundError:
            return None

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._values)

    @property
    def all(self) -> dict[str, T]:
        return dict(self._values)

    @property
    def count(self) -> int:
        return len(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __iter__(self) -> Iterator[T]:
        return iter(self._values.values())

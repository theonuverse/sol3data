"""Shared helpers and base classes used across the prydwen.gg scraping package.

These utilities remove the duplication that previously existed across
kit.py, build.py, and review.py: the "1-based indexed collection" pattern,
the "attribute-projection dict" pattern, and safe text extraction from
Playwright locators.

Requires Python 3.14+ (uses PEP 695 generic class syntax and deferred
annotation evaluation; no `from __future__ import annotations` needed).
"""
from collections.abc import Iterator

from playwright.sync_api import Locator


def safe_inner_text(locator: Locator, *, index: int = 0, default: str = "") -> str:
    """Return the stripped inner text of a locator, or ``default`` if it has no matches.

    Centralizes the "does this locator resolve to anything?" check that was
    previously repeated (with slightly different shapes) in build.py and kit.py.
    """
    if index < 0 or locator.count() <= index:
        return default
    return locator.nth(index).inner_text().strip()


class IndexedCollection[T]:
    """Base class for 1-based, lazily-fetched collections scraped from the DOM.

    Subclasses must implement :meth:`_count` and :meth:`_fetch`. This factors
    out the repeated ``get`` bounds-checking and ``all`` dict-building logic
    that appeared nearly identically in ``WeaponRecommendations``,
    ``EchoRecommendations``, ``EchoStats``, ``ResonanceChain``, and others.

    Uses PEP 695 generic syntax: ``class MyCollection(IndexedCollection[Item]):``.
    """

    _item_label: str = "Item"

    def _count(self) -> int:
        raise NotImplementedError

    def _fetch(self, index: int) -> T:
        """Fetch the item at a 1-based index. Bounds are already validated by ``get``."""
        raise NotImplementedError

    @property
    def count(self) -> int:
        """Total number of items in this collection."""
        return self._count()

    def get(self, index: int) -> T:
        """Retrieve an item by its 1-based index.

        Raises:
            ValueError: if ``index`` is outside ``[1, count]``.
        """
        total = self.count
        if index < 1 or index > total:
            raise ValueError(f"{self._item_label} index {index} out of bounds. Total available: {total}")
        return self._fetch(index)

    @property
    def all(self) -> dict[int, T]:
        """All items in the collection, keyed by 1-based index."""
        return {i: self._fetch(i) for i in range(1, self.count + 1)}

    def __len__(self) -> int:
        return self.count

    def __iter__(self) -> Iterator[T]:
        return iter(self.all.values())


class AttributeProjectingDict[T](dict[int, T]):
    """A dict[int, T] that can project a named attribute across all its values.

    Replaces the repeated ``WeaponRecommendationsDict`` / ``EchoRecommendationsDict``
    / ``EchoStatsDict`` subclasses, which each hardcoded the same
    ``{k: v.<attr> for k, v in self.items()}`` pattern per field.
    """

    def project(self, attribute: str) -> dict[int, object]:
        """Return ``{key: getattr(value, attribute) for key, value in self.items()}``."""
        return {key: getattr(value, attribute) for key, value in self.items()}


def make_projection_property(attribute: str) -> property:
    """Build a read-only property that projects ``attribute`` across an AttributeProjectingDict.

    Usage in a dict subclass::

        class WeaponRecommendationsDict(AttributeProjectingDict[WeaponRecommendationItem]):
            name = make_projection_property("name")
            information = make_projection_property("information")
    """

    def getter(self: AttributeProjectingDict) -> dict[int, object]:
        return self.project(attribute)

    return property(getter)

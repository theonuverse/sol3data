"""Top-level entry point for browsing prydwen.gg's Wuthering Waves character list."""
from playwright.sync_api import Page

from .._browser import BrowserSession
from .._normalization import character_slug
from .character import Character

_CHARACTERS_BOX_SELECTOR = ".employees-container.ww-cards .pw-card.avatar-card .emp-name"


class Characters(BrowserSession):
    """Browse the Wuthering Waves character roster on prydwen.gg."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._character_pages: dict[str, Page] = {}

    def get(self, name: str) -> Character:
        """Open a specific character's page by name (case-insensitive)."""
        slug = character_slug(name)
        url = f"https://www.prydwen.gg/wuthering-waves/characters/{slug}"
        page = self._character_pages.get(slug)
        if page is None or page.is_closed():
            for cached_page in self._character_pages.values():
                if not cached_page.is_closed():
                    cached_page.close()
            self._character_pages.clear()
            page = self._open(url)
            self._character_pages[slug] = page
        else:
            page.bring_to_front()
        return Character(page, slug=slug, url=url)

    def clear_cache(self, name: str | None = None) -> None:
        """Clear all cached pages or one canonical character page."""
        if name is None:
            for page in self._character_pages.values():
                if not page.is_closed():
                    page.close()
            self._character_pages.clear()
            return
        page = self._character_pages.pop(character_slug(name), None)
        if page is not None and not page.is_closed():
            page.close()

    @property
    def all(self) -> dict[int, str]:
        """All character names currently listed on the roster page, 1-based."""
        url = "https://www.prydwen.gg/wuthering-waves/characters"
        return {
            i: char.inner_text()
            for i, char in enumerate(
                self._open(url).locator(_CHARACTERS_BOX_SELECTOR).all(), 1
            )
        }

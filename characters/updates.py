"""Character page update metadata."""
from dataclasses import dataclass

from playwright.sync_api import Page

from ._common import safe_inner_text


@dataclass(frozen=True)
class CharacterUpdates:
    """The three update markers shown in the source page's Update Tracker."""

    review: str
    build_calculations: str
    profile: str
    last_updated: str

    @classmethod
    def from_page(cls, page: Page) -> "CharacterUpdates":
        tracker = page.locator(".last-update")
        return cls(
            review=safe_inner_text(tracker.locator(".review .info p")),
            build_calculations=safe_inner_text(tracker.locator(".build .info p")),
            profile=safe_inner_text(tracker.locator(".profile .info p")),
            last_updated=safe_inner_text(
                page.locator(".character-top .left-info p span")
            ),
        )

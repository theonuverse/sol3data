"""Scraping interface for a character's Review tab on prydwen.gg."""
from playwright.sync_api import Page

from ._common import IndexedCollection, safe_inner_text

_TAB_SELECTOR = ".tabs .single-tab"
_REVIEW_TAB_INDEX = 1  # 0-based: second tab on the character page

_TIER_LIST_SELECTOR = ".detailed-ratings.ww"
_REVIEW_PANEL_SELECTOR = ".tab-inside.active:visible"
_REVIEW_LIST_CSS = ".raw.list li"
_REVIEW_TEXT_CSS = ".review.raw"
_RATING_BOX_CONTAINER_CSS = ".rating-box-container"
_RATING_BOX_CSS = "div[class*='rating-box']"

_ROLE_CATEGORIES = ("DPS", "Hybrid", "Support")


class ModeRatings:
    """Tier ratings for a specific role, across game modes (TOA, Whimpering Wastes)."""

    def __init__(self, page: Page, list_selector: str, role_name: str, list_index: int) -> None:
        self._page = page
        self._list_selector = list_selector
        self._role_name = role_name
        self._list_index = list_index

    def _get_tier(self, container_index: int, mode_label: str) -> str:
        """Extract tier text from a specific game-mode container."""
        target_blocks = self._page.locator(f"h5:has-text('{self._role_name}') + {self._list_selector}")
        if target_blocks.count() <= self._list_index:
            raise ValueError(f"Role '{self._role_name}' with list index {self._list_index} does not exist.")

        target_block = target_blocks.nth(self._list_index)
        containers = target_block.locator(_RATING_BOX_CONTAINER_CSS)
        if containers.count() <= container_index:
            raise ValueError(f"{mode_label} rating is not available for role '{self._role_name}'.")

        return safe_inner_text(containers.nth(container_index).locator(_RATING_BOX_CSS))

    @property
    def toa(self) -> str:
        """Tower of Adversity tier rating."""
        return self._get_tier(0, "Tower of Adversity")

    @property
    def whiwa(self) -> str:
        """Whimpering Wastes tier rating."""
        return self._get_tier(1, "Whimpering Wastes")


class RoleCategories:
    """Dispatches tier-rating queries to the appropriate role category block."""

    def __init__(self, page: Page, list_selector: str, list_index: int) -> None:
        self._page = page
        self._list_selector = list_selector
        self._list_index = list_index

    def _has_role(self, role: str) -> bool:
        return self._page.locator(f"h5:has-text('{role}') + {self._list_selector}").count() > self._list_index

    def _role_ratings(self, role: str) -> ModeRatings:
        if not self._has_role(role):
            raise ValueError(f"'{role}' tier listing does not exist for this character configuration.")
        return ModeRatings(self._page, self._list_selector, role, self._list_index)

    @property
    def dps(self) -> ModeRatings:
        """DPS category tier ratings."""
        return self._role_ratings("DPS")

    @property
    def hybrid(self) -> ModeRatings:
        """Hybrid category tier ratings."""
        return self._role_ratings("Hybrid")

    @property
    def support(self) -> ModeRatings:
        """Support category tier ratings."""
        return self._role_ratings("Support")

    @property
    def available_roles(self) -> dict[int, str]:
        """Which of DPS/Hybrid/Support categories actually exist for this character, 1-based."""
        return {i: role for i, role in enumerate((r for r in _ROLE_CATEGORIES if self._has_role(r)), 1)}


class Ratings:
    """Access to both tier list variants (standard vs. value)."""

    def __init__(self, page: Page) -> None:
        self._page = page

    def _total_lists(self) -> int:
        return self._page.locator(_TIER_LIST_SELECTOR).count()

    def _role_categories(self, list_index: int, label: str) -> RoleCategories:
        if self._total_lists() <= list_index:
            raise ValueError(f"{label} tier list ratings do not exist on this page.")
        return RoleCategories(self._page, _TIER_LIST_SELECTOR, list_index=list_index)

    @property
    def tier_list(self) -> RoleCategories:
        """Standard tier list rankings."""
        return self._role_categories(0, "Standard")

    @property
    def value_tier_list(self) -> RoleCategories:
        """Value tier list rankings."""
        return self._role_categories(1, "Value")


class ReviewPoints(IndexedCollection[str]):
    """A single review section (Pros or Cons) as a 1-based collection of bullet points."""

    _item_label = "Review point"

    def __init__(self, page: Page, box_selector: str) -> None:
        self._page = page
        self._box_selector = box_selector

    def _get_box(self):
        box = self._page.locator(_REVIEW_PANEL_SELECTOR).locator(self._box_selector)
        if box.count() == 0:
            raise ValueError(f"Review points section '{self._box_selector}' does not exist.")
        return box

    def _count(self) -> int:
        return self._get_box().locator(_REVIEW_LIST_CSS).count()

    def _fetch(self, index: int) -> str:
        items = self._get_box().locator(_REVIEW_LIST_CSS)
        return items.nth(index - 1).inner_text().strip()


class Review:
    """Entry point for a character's Review tab: pros/cons, tier ratings, and full write-up."""

    def __init__(self, page: Page) -> None:
        self._page = page
        self._page.locator(_TAB_SELECTOR).nth(_REVIEW_TAB_INDEX).click()
        self.pros = ReviewPoints(page, ".box.pros")
        self.cons = ReviewPoints(page, ".box.cons")
        self.ratings = Ratings(page)

    @property
    def full_review(self) -> str:
        """The complete written review text."""
        review_element = self._page.locator(_REVIEW_PANEL_SELECTOR).locator(_REVIEW_TEXT_CSS)
        if review_element.count() == 0:
            raise ValueError("Full review text block does not exist for this character.")
        return review_element.inner_text().strip()

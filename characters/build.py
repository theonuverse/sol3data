"""Scraping interface for a character's Build tab on prydwen.gg."""
from playwright.sync_api import Locator, Page

from ._common import AttributeProjectingDict, IndexedCollection, make_projection_property, safe_inner_text

_MAIN_TAB_SELECTOR = ".tabs .single-tab"
_BUILD_TAB_INDEX = 2  # 0-based: third tab on the character page

_ACTIVE_TAB_SELECTOR = ".tab-inside.active:visible"
_SKILL_PRIORITY_BLOCK_SELECTOR = ".skill-priority"
_SKILL_SELECTOR = ".skill"
_SKILL_PRIORITY_LEVELS = 5

_BUILD_TIPS_SELECTOR = ".build-tips"
_WEAPON_TIPS_INDEX = 0
_ECHO_TIPS_INDEX = 1
_ECHO_STATS_TIPS_INDEX = 2


class WeaponPercentages(IndexedCollection[str]):
    """A weapon recommendation's performance percentage breakdown (usually 1 or 2 entries)."""

    _item_label = "Percentage"

    def __init__(self, item_locator: Locator) -> None:
        self._locator = item_locator.locator(".percentage p")

    def _count(self) -> int:
        return self._locator.count()

    def _fetch(self, index: int) -> str:
        return self._locator.nth(index - 1).inner_text().strip()


class WeaponRecommendationItem:
    """A single recommended weapon: name, performance percentage(s), and write-up."""

    def __init__(self, item_locator: Locator, info_locator: Locator | None) -> None:
        self._item = item_locator
        self._info = info_locator

    @property
    def name(self) -> str:
        """Name of the recommended weapon."""
        return safe_inner_text(self._item.locator(".ww-weapon-name"))

    @property
    def percentage(self) -> WeaponPercentages:
        """Performance percentage(s) for this weapon."""
        return WeaponPercentages(self._item)

    @property
    def information(self) -> str:
        """Review/description text explaining this weapon choice."""
        if self._info is None:
            return ""
        return safe_inner_text(self._info)


class WeaponRecommendationsDict(AttributeProjectingDict[WeaponRecommendationItem]):
    """dict[int, WeaponRecommendationItem] with attribute-projection shortcuts."""

    name = make_projection_property("name")
    information = make_projection_property("information")

    @property
    def percentage(self) -> dict[int, dict[int, str]]:
        """All weapons' percentage breakdowns, keyed by weapon index."""
        return {key: item.percentage.all for key, item in self.items()}


class WeaponRecommendations(IndexedCollection[WeaponRecommendationItem]):
    """Recommended weapons list, scoped to the first build-tips block."""

    _item_label = "Weapon recommendation"

    def __init__(self, page: Page) -> None:
        self._page = page
        self._container = page.locator(_BUILD_TIPS_SELECTOR).nth(_WEAPON_TIPS_INDEX)

    def _count(self) -> int:
        if self._container.count() == 0:
            return 0
        return self._container.locator(".single-item").count()

    def _fetch(self, index: int) -> WeaponRecommendationItem:
        item_locator = self._container.locator(".single-item").nth(index - 1)

        info_elements = self._container.locator(".information")
        info_locator = info_elements.nth(index - 1) if info_elements.count() >= index else None

        return WeaponRecommendationItem(item_locator, info_locator)

    @property
    def all(self) -> WeaponRecommendationsDict:
        """All weapon recommendations, keyed by 1-based index."""
        result = WeaponRecommendationsDict()
        for i in range(1, self.count + 1):
            result[i] = self._fetch(i)
        return result


class EchoRecommendationItem:
    """A single recommended Echo Set: name, rank, and write-up."""

    def __init__(self, item_locator: Locator, info_locator: Locator | None) -> None:
        self._item = item_locator
        self._info = info_locator

    @property
    def name(self) -> str:
        """Name of the recommended Echo Set (e.g. 'Rejuvenating Glow')."""
        name = safe_inner_text(self._item.locator(".ww-set-image"))
        if name:
            return name

        # Keep a text fallback for older or changed page markup.
        lines = [line.strip() for line in self._item.inner_text().splitlines() if line.strip()]
        if not lines:
            return ""
        if self.percentage and lines[0] == self.percentage:
            lines.pop(0)
        return lines[0] if lines else ""

    @property
    def percentage(self) -> str:
        """Rank/index string for this echo set (e.g. '1')."""
        return safe_inner_text(self._item.locator(".percentage p"))

    @property
    def information(self) -> str:
        """Review text and ideal main-echo/sub-stat guidance for this echo set."""
        if self._info is None:
            return ""
        return safe_inner_text(self._info)


class EchoRecommendationsDict(AttributeProjectingDict[EchoRecommendationItem]):
    """dict[int, EchoRecommendationItem] with attribute-projection shortcuts."""

    name = make_projection_property("name")
    percentage = make_projection_property("percentage")
    information = make_projection_property("information")


class EchoRecommendations(IndexedCollection[EchoRecommendationItem]):
    """Recommended Echo Sets list, scoped to the second build-tips block."""

    _item_label = "Echo recommendation"

    def __init__(self, page: Page) -> None:
        self._page = page
        self._container = page.locator(_BUILD_TIPS_SELECTOR).nth(_ECHO_TIPS_INDEX)

    def _count(self) -> int:
        if self._container.count() == 0:
            return 0
        return self._container.locator(".single-item").count()

    def _fetch(self, index: int) -> EchoRecommendationItem:
        item_locator = self._container.locator(".single-item").nth(index - 1)

        info_elements = self._container.locator(".information")
        info_locator = info_elements.nth(index - 1) if info_elements.count() >= index else None

        return EchoRecommendationItem(item_locator, info_locator)

    @property
    def all(self) -> EchoRecommendationsDict:
        """All echo recommendations, keyed by 1-based index."""
        result = EchoRecommendationsDict()
        for i in range(1, self.count + 1):
            result[i] = self._fetch(i)
        return result


class EchoStatItem:
    """A single main-stat slot (e.g. '4 cost' -> 'CRIT Rate / CRIT DMG')."""

    def __init__(self, box_locator: Locator) -> None:
        self._box = box_locator

    @property
    def cost(self) -> str:
        """Cost label for this slot (e.g. '4 cost', '3 cost')."""
        strong = self._box.locator("strong")
        if strong.count() > 0:
            return safe_inner_text(strong)
        return safe_inner_text(self._box.locator(".stats-inside"))

    @property
    def stats(self) -> str:
        """Recommended main stat(s) for this cost slot (e.g. 'Aero DMG')."""
        return safe_inner_text(self._box.locator(".list-stats"))


class EchoStatsDict(AttributeProjectingDict[EchoStatItem]):
    """dict[int, EchoStatItem] with attribute-projection shortcuts."""

    cost = make_projection_property("cost")
    stats = make_projection_property("stats")


class EchoStats(IndexedCollection[EchoStatItem]):
    """The 'Best Echo Stats' section, scoped to the third build-tips block."""

    _item_label = "Echo stat"

    def __init__(self, page: Page) -> None:
        self._page = page
        self._container = page.locator(_BUILD_TIPS_SELECTOR).nth(_ECHO_STATS_TIPS_INDEX)

    def _valid_boxes(self) -> list[Locator]:
        """Non-empty stat boxes from the main-stats grid."""
        if self._container.count() == 0:
            return []
        box_locator = self._container.locator(".main-stats .box")
        return [box_locator.nth(i) for i in range(box_locator.count()) if box_locator.nth(i).inner_text().strip()]

    def _count(self) -> int:
        return len(self._valid_boxes())

    def _fetch(self, index: int) -> EchoStatItem:
        return EchoStatItem(self._valid_boxes()[index - 1])

    @property
    def all(self) -> EchoStatsDict:
        """All valid main-stat slots, keyed by 1-based index."""
        result = EchoStatsDict()
        for i in range(1, self.count + 1):
            result[i] = self._fetch(i)
        return result

    @property
    def substats(self) -> str:
        """Recommended Substats priority text, below the main-stats grid."""
        if self._container.count() == 0:
            return ""
        return safe_inner_text(self._container.locator(".flex.flex-wrap.gap-6"))


class EndgameStats:
    """The 'Best Endgame Stats' section from the character analysis block."""

    def __init__(self, page: Page) -> None:
        self._page = page
        self._locator = page.locator(".tab-inside.active .section-analysis")

    @property
    def exists(self) -> bool:
        """Whether the endgame stats block is present on the page."""
        return self._locator.count() > 0

    @property
    def text(self) -> str:
        """The entire endgame stats block as raw text, preserving newlines."""
        if not self.exists:
            return ""
        return self._locator.inner_text().strip()

    @property
    def lines(self) -> list[str]:
        """The stats block split into non-empty, stripped lines."""
        return [line.strip() for line in self.text.splitlines() if line.strip()]


class BuildRole:
    """Skills sorted by priority (1-5) for a specific role block."""

    def __init__(self, locator: Locator, role_name: str) -> None:
        self._locator = locator
        self.role = role_name

    def get(self, index: int) -> str | None:
        """Skill at the given priority position (1-5), or ``None`` if absent."""
        if not (1 <= index <= _SKILL_PRIORITY_LEVELS):
            raise ValueError(f"Priority index must be between 1 and {_SKILL_PRIORITY_LEVELS}. Got: {index}")

        skill_element = self._locator.locator(_SKILL_SELECTOR).nth(index - 1)
        if skill_element.count() == 0:
            return None
        return skill_element.inner_text().strip()

    @property
    def all(self) -> dict[int, str | None]:
        """All skills sorted by priority."""
        if self.get(1) is None:
            return {}
        return {i: self.get(i) for i in range(1, _SKILL_PRIORITY_LEVELS + 1)}


class SkillPriority:
    """Maps available skill-priority role blocks, resolving role names with DOM fallbacks."""

    def __init__(self, page: Page) -> None:
        self._page = page
        self._active_tab = page.locator(_ACTIVE_TAB_SELECTOR)
        self._global_role_selector = ".role"

    @property
    def count(self) -> int:
        """Total number of skill priority blocks available."""
        return self._active_tab.locator(_SKILL_PRIORITY_BLOCK_SELECTOR).count()

    def _get_global_roles(self) -> list[str]:
        """Fallback role names from the page-level `.role` elements (dual-count layout)."""
        dom_count = self._page.locator(self._global_role_selector).count()
        if dom_count == 0:
            return []

        roles = [safe_inner_text(self._page.locator(self._global_role_selector), index=0)]
        if dom_count != 2:
            roles.append(safe_inner_text(self._page.locator(self._global_role_selector), index=1))
        return roles

    def get(self, index: int) -> BuildRole:
        """The BuildRole at the given 1-based block index.

        Raises:
            ValueError: if ``index`` is less than 1 or the block does not exist.
        """
        if index < 1:
            raise ValueError(f"Index must be 1 or greater. Got: {index}")

        block_locator = self._active_tab.locator(_SKILL_PRIORITY_BLOCK_SELECTOR).nth(index - 1)
        if block_locator.count() == 0:
            raise ValueError(f"Skill priority block with index {index} does not exist for this character.")

        role_name = self._resolve_role_name(index)
        return BuildRole(block_locator, role_name)

    def _resolve_role_name(self, index: int) -> str:
        """Resolve a role name for block `index`, preferring an adjacent <h5>, else global roles."""
        h5_locator = self._active_tab.locator(f"h5:has(+ {_SKILL_PRIORITY_BLOCK_SELECTOR})").nth(index - 1)
        if h5_locator.count() > 0:
            return h5_locator.inner_text().strip()

        global_roles = self._get_global_roles()
        if len(global_roles) == 2:
            return "/".join(global_roles)
        if len(global_roles) == 1:
            return global_roles[0]
        return "Default"


class Build:
    """Entry point for a character's Build tab (weapons, echoes, stats, skill priority)."""

    def __init__(self, page: Page) -> None:
        self._page = page
        self._page.locator(_MAIN_TAB_SELECTOR).nth(_BUILD_TAB_INDEX).click()
        self.weapon_recommendations = WeaponRecommendations(self._page)
        self.echo_recommendations = EchoRecommendations(self._page)
        self.echo_stats = EchoStats(self._page)
        self.endgame_stats = EndgameStats(self._page)
        self.skill_priority = SkillPriority(self._page)

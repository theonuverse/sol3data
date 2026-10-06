"""Scraping interface for a character's Kit tab on prydwen.gg (skills, chain, materials)."""
from playwright.sync_api import Page

from ._common import IndexedCollection, safe_inner_text

_MAIN_TAB_SELECTOR = ".tabs .single-tab"
_KIT_TAB_INDEX = 0  # 0-based: first tab on the character page

_SKILL_CATEGORY_TAB_SELECTOR = ".tabs-skills .single-tab"
_SKILL_PANEL_SELECTOR = ".tab-inside.active:has(.tabs-skills) .tab-inside.active"

_SKILL_BOX_CSS = ".box.skill-new"
_SKILL_NAME_CSS = ".skill-info"
_SKILL_DESC_CSS = ".skill-with-coloring"
_SKILL_MULTIPLIER_CSS = ".pw-accordion-body"
_MAX_MULTIPLIER_LEVELS = 10

_RESONANCE_CHAIN_SELECTOR = ".skills.dupes .box"
_RS_SEQUENCE_CSS = ".skill-icon"
_RS_NAME_CSS = ".skill-info"
_RS_DESCRIPTION_CSS = ".skill-with-coloring"

_UPGRADE_BOX_SELECTOR = ".upgrade-materials .box"

_PASSIVE_CATEGORY_INDEX = 1
_PASSIVES_WITH_TUNE_COUNT = 4


class Multipliers:
    """Skill multiplier values indexed by scaling level (1-based)."""

    def __init__(self, data: dict[int, str]) -> None:
        self._data = data

    def get(self, level: int) -> str:
        """Retrieve the multiplier value for a specific level."""
        if level not in self._data:
            raise ValueError(f"Multiplier level {level} does not exist. Available levels: {sorted(self._data)}")
        return self._data[level]

    @property
    def all(self) -> dict[int, str]:
        """All level-to-multiplier mappings."""
        return dict(self._data)

    def __repr__(self) -> str:
        return f"Multipliers({self._data!r})"


class Skill:
    """A single character skill with its metadata and level-based scaling data."""

    def __init__(self, category: str, name: str, description: str, multipliers: Multipliers) -> None:
        self.category = category
        self.name = name
        self.description = description
        self.multipliers = multipliers

    def __repr__(self) -> str:
        return f"Skill(name={self.name!r}, category={self.category!r})"


class ActiveSkills:
    """Basic Attack, Resonance Skill, and Resonance Liberation."""

    def __init__(self, skills: "Skills") -> None:
        self._skills = skills

    @property
    def basic_attack(self) -> Skill:
        """The Basic Attack skill."""
        return self._skills._fetch(0, 1)

    @property
    def resonance_skill(self) -> Skill:
        """The Resonance Skill."""
        return self._skills._fetch(0, 2)

    @property
    def resonance_liberation(self) -> Skill:
        """The Resonance Liberation (ultimate) skill."""
        return self._skills._fetch(0, 3)


class PassiveSkills:
    """Forte Circuit, its optional Tune, and the two Inherent Skills.

    Whether a "Forte Circuit Tune" exists shifts the DOM index of the two
    Inherent Skills, so the box count is checked lazily on each access
    rather than cached, since it is cheap and avoids stale-state bugs.
    """

    def __init__(self, skills: "Skills") -> None:
        self._skills = skills

    def _box_count(self) -> int:
        """Total passive skill boxes for this character (3 or 4)."""
        self._skills._page.locator(_SKILL_CATEGORY_TAB_SELECTOR).nth(_PASSIVE_CATEGORY_INDEX).click()
        return self._skills._page.locator(_SKILL_PANEL_SELECTOR).locator(_SKILL_BOX_CSS).count()

    @property
    def has_tune(self) -> bool:
        """Whether this character has a Forte Circuit Tune passive."""
        return self._box_count() == _PASSIVES_WITH_TUNE_COUNT

    @property
    def forte_circuit(self) -> Skill:
        """The Forte Circuit passive."""
        return self._skills._fetch(_PASSIVE_CATEGORY_INDEX, 1)

    @property
    def forte_circuit_tune(self) -> Skill:
        """The Forte Circuit Tune passive.

        Raises:
            ValueError: if this character has no Forte Circuit Tune.
        """
        if not self.has_tune:
            raise ValueError("Forte Circuit Tune does not exist for this character.")
        return self._skills._fetch(_PASSIVE_CATEGORY_INDEX, 2)

    @property
    def inherent_skill_1(self) -> Skill:
        """The first Inherent Skill."""
        return self._skills._fetch(_PASSIVE_CATEGORY_INDEX, 3 if self.has_tune else 2)

    @property
    def inherent_skill_2(self) -> Skill:
        """The second Inherent Skill."""
        return self._skills._fetch(_PASSIVE_CATEGORY_INDEX, 4 if self.has_tune else 3)


class ConcertoSkills:
    """Intro and Outro skills."""

    def __init__(self, skills: "Skills") -> None:
        self._skills = skills

    @property
    def intro_skill(self) -> Skill:
        """The Intro Skill."""
        return self._skills._fetch(2, 1)

    @property
    def outro_skill(self) -> Skill:
        """The Outro Skill."""
        return self._skills._fetch(2, 2)


class Skills:
    """Entry point for a character's Active, Passive, and Concerto skill categories."""

    def __init__(self, page: Page) -> None:
        self._page = page
        self.active = ActiveSkills(self)
        self.passive = PassiveSkills(self)
        self.concerto = ConcertoSkills(self)

    def _fetch(self, category_index: int, box_index: int) -> Skill:
        """Navigate to a skill category tab and scrape a specific skill box (1-based)."""
        self._page.locator(_SKILL_CATEGORY_TAB_SELECTOR).nth(category_index).click()
        category = safe_inner_text(self._page.locator(_SKILL_CATEGORY_TAB_SELECTOR).nth(category_index))

        panel = self._page.locator(_SKILL_PANEL_SELECTOR)
        boxes = panel.locator(_SKILL_BOX_CSS)
        if box_index < 1 or box_index > boxes.count():
            raise ValueError(f"Skill box index {box_index} out of bounds for category index {category_index}.")

        skill = boxes.nth(box_index - 1)
        name = safe_inner_text(skill.locator(_SKILL_NAME_CSS))
        description = safe_inner_text(skill.locator(_SKILL_DESC_CSS))
        multipliers = self._fetch_multipliers(skill)

        return Skill(category, name, description, Multipliers(multipliers))

    @staticmethod
    def _fetch_multipliers(skill_locator) -> dict[int, str]:
        """Expand the multiplier slider (if present) and record the value at each level."""
        button = skill_locator.locator("button")
        if button.count() == 0:
            return {}

        button.click()
        slider = skill_locator.locator("[role='slider']")
        slider.click()

        values: dict[int, str] = {}
        for level in range(1, _MAX_MULTIPLIER_LEVELS + 1):
            if level > 1:
                slider.press("ArrowRight")
            values[level] = safe_inner_text(skill_locator.locator(_SKILL_MULTIPLIER_CSS))
        return values


class ResonanceChainNode:
    """A single node in a character's resonance chain (constellation)."""

    def __init__(self, sequence: str, name: str, description: str) -> None:
        self.sequence = sequence
        self.name = name
        self.description = description

    def __repr__(self) -> str:
        return f"ResonanceChainNode(sequence={self.sequence!r}, name={self.name!r})"


class ResonanceChain(IndexedCollection[ResonanceChainNode]):
    """A character's resonance chain (constellation) nodes, 1-based."""

    _item_label = "Resonance chain node"

    def __init__(self, page: Page) -> None:
        self._page = page

    def _count(self) -> int:
        return self._page.locator(_RESONANCE_CHAIN_SELECTOR).count()

    def _fetch(self, index: int) -> ResonanceChainNode:
        node = self._page.locator(_RESONANCE_CHAIN_SELECTOR).nth(index - 1)
        return ResonanceChainNode(
            sequence=safe_inner_text(node.locator(_RS_SEQUENCE_CSS)),
            name=safe_inner_text(node.locator(_RS_NAME_CSS)),
            description=safe_inner_text(node.locator(_RS_DESCRIPTION_CSS)),
        )


class Material:
    """A single upgrade material requirement (name + quantity)."""

    def __init__(self, name: str, quantity: str) -> None:
        self.name = name
        self.quantity = quantity

    def __repr__(self) -> str:
        return f"Material(name={self.name!r}, quantity={self.quantity!r})"


class UpgradeCategory(IndexedCollection[Material]):
    """A single category of upgrade materials (e.g. Character Ascension, Skill Upgrades)."""

    _item_label = "Material"

    def __init__(self, page: Page, box_index: int) -> None:
        """``box_index`` is 0-based, matching its position among upgrade-material boxes."""
        self._page = page
        self._box_index = box_index

    def _get_box(self):
        boxes = self._page.locator(_UPGRADE_BOX_SELECTOR)
        if boxes.count() <= self._box_index:
            raise ValueError(f"Upgrade category box index {self._box_index} does not exist.")
        return boxes.nth(self._box_index)

    @property
    def name(self) -> str:
        """The name of this upgrade category."""
        return safe_inner_text(self._get_box().locator("h5"))

    def _count(self) -> int:
        return self._get_box().locator("li").count()

    def _fetch(self, index: int) -> Material:
        item = self._get_box().locator("li").nth(index - 1)
        return Material(
            name=safe_inner_text(item.locator("strong[class*='rarity-']")),
            quantity=safe_inner_text(item.locator("strong")),
        )


class UpgradeMaterials:
    """Entry point for a character's upgrade material categories."""

    def __init__(self, page: Page) -> None:
        self._page = page

    @property
    def count(self) -> int:
        """Number of upgrade-material category boxes present."""
        return self._page.locator(_UPGRADE_BOX_SELECTOR).count()

    def _category(self, box_index: int, label: str) -> UpgradeCategory:
        if self.count <= box_index:
            raise ValueError(f"{label} materials block does not exist.")
        return UpgradeCategory(self._page, box_index)

    @property
    def character_ascension(self) -> UpgradeCategory:
        """Character ascension material category."""
        return self._category(0, "Character ascension")

    @property
    def skill_upgrades(self) -> UpgradeCategory:
        """Skill upgrade material category."""
        return self._category(1, "Skill upgrade")


class Kit:
    """Entry point for a character's complete Kit tab (skills, chain, materials)."""

    def __init__(self, page: Page) -> None:
        self._page = page
        self._page.locator(_MAIN_TAB_SELECTOR).nth(_KIT_TAB_INDEX).click()
        self.skills = Skills(self._page)
        self.resonance_chain = ResonanceChain(self._page)
        self.upgrade_materials = UpgradeMaterials(self._page)

"""Gameplay, rotation, synergy, and team information for a character."""
from dataclasses import dataclass

from playwright.sync_api import Locator, Page

from ._common import safe_inner_text
from ._page import active_panel, wait_for_panel_content

_MAIN_TAB_SELECTOR = ".tabs .single-tab"
_GAMEPLAY_TAB_TEXT = "GAMEPLAY AND TEAMS"
_ACTIVE_PANEL_SELECTOR = ".tab-inside.active:visible"


def _click_gameplay_tab(page: Page) -> Locator:
    tabs = page.locator(_MAIN_TAB_SELECTOR).filter(has_text=_GAMEPLAY_TAB_TEXT)
    if tabs.count() == 0:
        raise ValueError("Gameplay and Teams tab is not available for this character.")
    tabs.first.click()
    return wait_for_panel_content(active_panel(page))


def _heading_sections(panel: Locator) -> dict[str, str]:
    """Return text grouped under each h5/h6 heading in the active panel."""
    return panel.evaluate(
        """panel => {
            const result = {};
            const headings = [...panel.querySelectorAll('h5, h6')].filter((heading) => {
                return heading.parentElement?.classList.contains('rte-plain');
            });
            for (const heading of headings) {
                const parts = [];
                let node = heading.nextElementSibling;
                while (node && !['H5', 'H6'].includes(node.tagName)) {
                    const text = node.innerText?.trim();
                    if (text) parts.push(text);
                    node = node.nextElementSibling;
                }
                const title = heading.innerText.trim().replace(/^[^\\w]+/, '').replace(/:$/, '');
                result[title] = parts.join('\\n\\n');
            }
            for (const callout of panel.querySelectorAll('.callout')) {
                const heading = callout.querySelector('h5, h6');
                if (heading) {
                    const clone = callout.cloneNode(true);
                    clone.querySelectorAll('h5, h6').forEach(node => node.remove());
                    result[heading.innerText.trim()] = clone.innerText.trim();
                }
            }
            return result;
        }"""
    )


@dataclass(frozen=True)
class Rotation:
    """A normalized rotation guide."""

    name: str
    steps: list[str]
    notes: str


@dataclass(frozen=True)
class SynergyGroups:
    """Role-aware team recommendations for the current character."""

    dps: list[str]
    sub_dps: list[str]
    supports: list[str]

    @property
    def all(self) -> dict[str, list[str]]:
        return {
            "dps": self.dps,
            "sub_dps": self.sub_dps,
            "supports": self.supports,
        }


class Gameplay:
    """Access a character's gameplay guide and team recommendations."""

    def __init__(self, page: Page) -> None:
        self._page = page

    def _sections(self) -> dict[str, str]:
        return _heading_sections(_click_gameplay_tab(self._page))

    @property
    def how_to_play(self) -> str:
        """General rotation and gameplay explanation."""
        sections = self._sections()
        for title, text in sections.items():
            if "rotation" in title.lower() and "how to play" in title.lower():
                return text
        return ""

    @property
    def echo_timing(self) -> str:
        """Optional Echo timing advice."""
        sections = self._sections()
        return next((text for title, text in sections.items() if "echo timing" in title.lower()), "")

    @property
    def rotations(self) -> dict[str, str]:
        """Named rotation instructions, keyed by normalized rotation title."""
        sections = self._sections()
        rotations: dict[str, str] = {}
        action_prefixes = (
            "intro", "basic", "heavy", "ultimate", "hold ultimate", "skill",
            "outro", "dash", "dodge", "jump", "tune break",
        )
        for title, text in sections.items():
            normalized_title = title.lower()
            if "how to play" in normalized_title or normalized_title.endswith("& gameplay"):
                continue
            if not (
                "rotation" in normalized_title
                or "opener" in normalized_title
                or normalized_title.startswith(("easy", "standard"))
            ):
                continue
            if not any(line.strip().lower().startswith(action_prefixes) for line in text.splitlines()):
                continue
            rotations[title] = text
        return rotations

    @property
    def rotation_guides(self) -> dict[str, Rotation]:
        """Structured rotations with action steps separated from explanatory notes."""
        action = ("intro", "basic", "heavy", "ultimate", "hold ultimate", "skill",
                  "outro", "dash", "dodge", "jump", "tune break")
        guides: dict[str, Rotation] = {}
        for title, text in self.rotations.items():
            steps: list[str] = []
            notes: list[str] = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                if line.lower().startswith(action):
                    steps.append(line)
                else:
                    notes.append(line)
            guides[title] = Rotation(title, steps, "\n\n".join(notes))
        return guides

    @property
    def additional_tips(self) -> str:
        """Optional additional gameplay tips."""
        sections = self._sections()
        return next((text for title, text in sections.items() if "additional tips" in title.lower()), "")

    @property
    def synergies(self) -> SynergyGroups:
        """Synergies grouped by DPS, sub-DPS, and support/healer roles.

        The current character is included in the category matching its own
        site role. The remaining groups are mapped relative to that role so a
        support character is not presented as a DPS.
        """
        panel = _click_gameplay_tab(self._page)
        groups: list[list[str]] = []
        for item in panel.locator("li").all():
            names = []
            for image in item.locator("img[alt]").all():
                name = (image.get_attribute("alt") or "").strip()
                if name and name not in {"Set", "Echo"} and name not in names:
                    names.append(name)
            if names:
                groups.append(names)
        role_text = " ".join(
            safe_inner_text(locator)
            for locator in self._page.locator(".role").all()
        ).casefold()
        character_name = safe_inner_text(
            self._page.locator(".character-top .left-info strong")
        )
        is_dps = "dps" in role_text and "support" not in role_text
        is_support = "support" in role_text or "healer" in role_text
        is_hybrid = "hybrid" in role_text
        if is_dps:
            return SynergyGroups(
                dps=[character_name] if character_name else [],
                sub_dps=groups[0] if groups else [],
                supports=groups[1] if len(groups) > 1 else [],
            )
        if is_support:
            return SynergyGroups(
                dps=groups[0] if groups else [],
                sub_dps=groups[1] if len(groups) > 1 else [],
                supports=[character_name] if character_name else [],
            )
        if is_hybrid:
            return SynergyGroups(
                dps=groups[0] if groups else [],
                sub_dps=[character_name] if character_name else [],
                supports=groups[1] if len(groups) > 1 else [],
            )
        return SynergyGroups(
            dps=groups[0] if groups else [],
            sub_dps=groups[1] if len(groups) > 1 else [],
            supports=[character_name] if character_name else [],
        )

    @property
    def team_compositions(self) -> dict[int, list[str]]:
        """Example teams, represented by their character names in display order."""
        panel = _click_gameplay_tab(self._page)
        images = panel.locator("img[alt]")
        character_name = safe_inner_text(self._page.locator(".character-top .left-info strong"))
        groups: list[list[str]] = []
        current: list[str] = []
        started = False
        for index in range(images.count()):
            name = (images.nth(index).get_attribute("alt") or "").strip()
            if not name or name in {"Set", "Echo"}:
                continue
            if name == character_name:
                if started and current:
                    groups.append(current)
                    current = []
                started = True
            if started and name not in current:
                current.append(name)
        if current:
            groups.append(current)
        return {index: team for index, team in enumerate(groups, 1)}

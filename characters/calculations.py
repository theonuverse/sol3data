"""Damage calculation data for a character."""
from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from playwright.sync_api import Locator, Page

from .._collections import NamedCollection
from ._common import safe_inner_text
from ._page import active_panel, wait_for_panel_content

_MAIN_TAB_SELECTOR = ".tabs .single-tab"
_CALCULATIONS_TAB_TEXT = "CALCULATIONS"
_ACTIVE_PANEL_SELECTOR = ".tab-inside.active:visible"
_DAMAGE_ROW = re.compile(
    r"\(S(?P<sequence>[0-6])\)\s+(?P<damage>[\d,.]+)\s+DMG\s+\((?P<dps>[\d,.]+)\s+DPS\)\s*(?P<percent>[\d.]+%)?"
)


@dataclass(frozen=True)
class SequenceDamage:
    """Damage and DPS for one sequence level."""

    sequence: int
    damage: str
    dps: str
    percentage: str


@dataclass(frozen=True)
class CalculationTeamMember:
    """A teammate and the weapon, Echo set, and main Echo used with them."""

    character: str
    weapon: str
    echo_set: str
    main_echo: str


class CalculationTeam(NamedCollection[CalculationTeamMember]):
    """The teammates whose buffs are included in a calculation."""

    def __init__(self, members: tuple[CalculationTeamMember, ...]) -> None:
        super().__init__(
            {member.character: member for member in members},
            label="Calculation teammate",
        )


class SequenceDamages:
    """S0-S6 values accessed by sequence level."""

    def __init__(self, values: dict[int, SequenceDamage]) -> None:
        self._values = values

    def get(self, sequence: int) -> SequenceDamage:
        if sequence not in range(7):
            raise ValueError(f"Sequence must be between 0 and 6. Got: {sequence}")
        try:
            return self._values[sequence]
        except KeyError as error:
            raise ValueError(f"S{sequence} calculation is not available.") from error

    @property
    def all(self) -> dict[int, SequenceDamage]:
        return dict(self._values)

    def __iter__(self) -> Iterator[SequenceDamage]:
        """Iterate through the available sequence results."""
        return iter(self._values.values())

@dataclass(frozen=True)
class DamageProfile:
    """Damage totals and relative contributions grouped by attack type."""

    raw_values: dict[str, str]
    percentages: dict[str, str]

    def get(self, attack_type: str) -> str:
        """Return the raw total for an attack type."""
        normalized = attack_type.casefold()
        for name, value in self.raw_values.items():
            if name.casefold() == normalized:
                return value
        raise ValueError(f"Damage profile entry '{attack_type}' does not exist.")

    def get_percentage(self, attack_type: str) -> str:
        """Return an attack type's relative contribution."""
        normalized = attack_type.casefold()
        for name, value in self.percentages.items():
            if name.casefold() == normalized:
                return value
        raise ValueError(f"Damage profile entry '{attack_type}' does not exist.")

    @property
    def total(self) -> str:
        """Return the raw total across all attack types."""
        total = sum(_number(value) for value in self.raw_values.values())
        return f"{total:,.0f}"


class TeamBuild:
    """Named access to the character, weapon, and Echo build entries."""

    def __init__(self, values: dict[int, str]) -> None:
        self._values = values

    def get(self, index: int) -> str:
        try:
            return self._values[index]
        except KeyError as error:
            raise ValueError(f"Team build entry {index} does not exist.") from error

    @property
    def all(self) -> dict[int, str]:
        return dict(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __iter__(self) -> Iterator[str]:
        return iter(self._values.values())


def _number(value: str) -> float:
    return float(re.sub(r"[^\d.]", "", value) or 0)


def _make_damage_profile(values: dict[str, str]) -> DamageProfile:
    total = sum(_number(value) for value in values.values())
    percentages = {
        key: f"{(_number(value) / total * 100):.2f}%" if total else "0.00%"
        for key, value in values.items()
    }
    return DamageProfile(dict(values), percentages)


def _read_damage_profile(table: Locator) -> dict[str, str]:
    values: dict[str, str] = {}
    if table.count() == 0:
        return values
    for row in table.last.locator("tr").all():
        cells = row.locator("th, td")
        if cells.count() >= 2:
            key = safe_inner_text(cells.nth(0))
            value = safe_inner_text(cells.nth(1))
            if key and value.casefold() != "dmg" and _number(value) > 0:
                values[key] = value
    return values


class CalculationScenario:
    """A single target/mode calculation scenario."""

    def __init__(self, locator: Locator) -> None:
        self._locator = locator

    @property
    def name(self) -> str:
        return safe_inner_text(self._locator.locator("h5, h6").first)

    @property
    def text(self) -> str:
        return self._locator.inner_text().strip()

    @property
    def rotation_time(self) -> str:
        match = re.search(r"Rotation time:\s*([^\n]+)", self.text, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    @property
    def sequence_damage(self) -> SequenceDamages:
        result: dict[int, SequenceDamage] = {}
        text = re.sub(r"\s+", " ", self.text)
        for match in _DAMAGE_ROW.finditer(text):
            sequence = int(match.group("sequence"))
            result[sequence] = SequenceDamage(
                sequence=sequence,
                damage=match.group("damage"),
                dps=match.group("dps"),
                percentage=match.group("percent") or "",
            )
        return SequenceDamages(result)

    @property
    def damage_profile(self) -> DamageProfile:
        return _make_damage_profile(_read_damage_profile(self._locator.locator("table")))

    def get(self, sequence: int) -> SequenceDamage:
        """Retrieve one sequence result without direct indexing."""
        return self.sequence_damage.get(sequence)


class CalculationMode:
    """Calculations for one mode, such as Unison or Electro Flare."""

    def __init__(self, page: Page, tab: Locator | None = None) -> None:
        self._page = page
        self._tab = tab

    @property
    def name(self) -> str:
        """Mode label, such as ``Unison`` or ``Electro Flare``."""
        return safe_inner_text(self._tab) if self._tab is not None else "Default"

    def __repr__(self) -> str:
        return f"CalculationMode(name={self.name!r})"

    def _panel(self) -> Locator:
        if self._tab is not None:
            self._tab.click()
        else:
            tabs = self._page.locator(_MAIN_TAB_SELECTOR).filter(has_text=_CALCULATIONS_TAB_TEXT)
            tabs.first.click()
        self._page.wait_for_timeout(1500)
        return self._page.locator(_ACTIVE_PANEL_SELECTOR)

    @property
    def text(self) -> str:
        return self._panel().inner_text().strip()

    @property
    def calculation_information(self) -> CalculationTeam:
        """Teammate buffs included in this calculation set."""
        panel = self._panel()
        heading = panel.get_by_text("Calculations information", exact=True).first
        if heading.count() == 0:
            return CalculationTeam(())
        members: list[CalculationTeamMember] = []
        for item in heading.locator("xpath=following-sibling::ul[1]/li").all():
            character = safe_inner_text(item.locator("a .inline-name").first)
            weapon = safe_inner_text(item.locator("strong").first)
            echo_set = safe_inner_text(item.locator(".ww-set-min p").first)
            main_echo = safe_inner_text(item.locator(".ww-echo-name span").first)
            if character:
                members.append(CalculationTeamMember(character, weapon, echo_set, main_echo))
        return CalculationTeam(tuple(members))

    @property
    def calculation_team(self) -> CalculationTeam:
        """Alias for :attr:`calculation_information`."""
        return self.calculation_information

    @property
    def team_build(self) -> TeamBuild:
        """Character, weapon, Echo set, and main Echo image labels used for buffs."""
        panel = self._panel()
        names: list[str] = []
        for image in panel.locator("img[alt]").all():
            name = (image.get_attribute("alt") or "").strip()
            if name and name not in {"Set", "Echo"} and name not in names:
                names.append(name)
        return TeamBuild({index: name for index, name in enumerate(names, 1)})

    @property
    def damage_profile(self) -> DamageProfile:
        """Basic, heavy, skill, liberation, outro, and Echo damage totals."""
        panel = self._panel()
        return _make_damage_profile(_read_damage_profile(panel.locator("table")))

    @property
    def rotation_time(self) -> str:
        """Rotation duration for the primary scenario in this calculation set."""
        scenarios = self.scenarios
        primary = next(iter(scenarios.values()), None)
        return primary.rotation_time if primary is not None else ""

    @property
    def sequence_damage(self) -> SequenceDamages:
        """S0-S6 damage for the primary scenario."""
        scenarios = self.scenarios
        primary = next(iter(scenarios.values()), None)
        return primary.sequence_damage if primary is not None else SequenceDamages({})

    @property
    def scenarios(self) -> dict[int, CalculationScenario]:
        panel = self._panel()
        headings = panel.locator("h5, h6").filter(has_text=re.compile(r"scenario", re.IGNORECASE))
        scenarios: dict[int, CalculationScenario] = {}
        for index in range(headings.count()):
            box = headings.nth(index).locator("xpath=ancestor::div[contains(@class, 'box')][1]")
            scenarios[index + 1] = CalculationScenario(box)
        return scenarios

    def get(self, scenario: int) -> CalculationScenario:
        """Retrieve a scenario by its 1-based number."""
        try:
            return self.scenarios[scenario]
        except KeyError as error:
            raise ValueError(f"Calculation scenario {scenario} does not exist.") from error


class CalculationModes(NamedCollection[CalculationMode]):
    """Named calculation modes with standardized string lookup."""

    def __init__(self, values: dict[str, CalculationMode]) -> None:
        super().__init__(values, label="Calculation mode")

    def get(self, name: str) -> CalculationMode:
        """Return a calculation mode with an explicit concrete type."""
        return super().get(name)


class Calculations:
    """Access all calculation modes and their damage profiles."""

    def __init__(self, page: Page) -> None:
        self._page = page

    @property
    def additional_information(self) -> str:
        """Global explanation of how the site's damage simulations are produced."""
        panel = self._open()
        heading = panel.get_by_text("Additional information", exact=True).first
        if heading.count() == 0:
            return ""
        paragraphs = heading.locator("xpath=following-sibling::p").all_inner_texts()
        return "\n\n".join(text.strip() for text in paragraphs if text.strip())

    @property
    def modes(self) -> CalculationModes:
        panel = self._open()
        tabs = panel.locator("[role='tab']")
        if tabs.count() == 0:
            return CalculationModes({"Default": CalculationMode(self._page)})
        values = {
            safe_inner_text(tabs.nth(index)): CalculationMode(self._page, tabs.nth(index))
            for index in range(tabs.count())
        }
        return CalculationModes(values)

    @property
    def mode_names(self) -> tuple[str, ...]:
        """Visible names of all selectable modes."""
        return self.modes.names

    @property
    def mode(self) -> CalculationMode:
        """The calculation object for a single-mode character."""
        modes = self.modes
        if len(modes) > 1:
            raise ValueError("This character has multiple calculation modes; use modes or get().")
        return modes.get(modes.names[0])

    def get(self, name: str) -> CalculationMode:
        """Get a named calculation mode, case-insensitively."""
        return self.modes.get(name)

    def __iter__(self) -> Iterator[CalculationMode]:
        return iter(self.modes)

    def _open(self) -> Locator:
        tabs = self._page.locator(_MAIN_TAB_SELECTOR).filter(has_text=_CALCULATIONS_TAB_TEXT)
        if tabs.count() == 0:
            raise ValueError("Calculations tab is not available for this character.")
        tabs.first.click()
        self._page.wait_for_timeout(2000)
        return wait_for_panel_content(active_panel(self._page))

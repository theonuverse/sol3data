# `sol3data`

A Python API for fetching Wuthering Waves data from [prydwen.gg](https://www.prydwen.gg) and [wuthering.gg](https://wuthering.gg/), built with Playwright.

## Installation

Activate virtual environment

```bash
python3 -m venv .env
source .env/bin/activate
pip install playwright playwright-stealth
playwright install
git clone https://github.com/theonuverse/sol3data.git
```

Or optionally if you use Termux, you can use this Dockerfile together with PRoot Distro to automatically set the environment up.

```bash
FROM debian:13-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN \
        apt-get update && apt-get upgrade -y && \
        apt-get install python3 python3-pip git -y && \
        pip install playwright playwright-stealth --break-system-packages && \
        playwright install-deps && \
        playwright install chromium

WORKDIR /root

RUN git clone https://github.com/theonuverse/sol3data.git

CMD ["/bin/bash"]
```

Then build it, install it and run it.

```bash
pd build -t sol3data:latest --install-as sol3data --no-cache .
pd sh sol3data
```

## Usage

```python
from sol3data import Characters

# Explicit lifecycle: no context manager is required.
chars = Characters()
char = chars.get("iuno")

# fetch character details
print(char.name)
print(char.introduction)
print(char.updates.review)
print(char.updates.build_calculations)
print(char.updates.profile)
print(char.role.all)  # dict of role(s), e.g. {1: "Main DPS"}

# The rest of the API is organized by page section:
skill = char.kit.skills.active.basic_attack
print(skill.name, skill.description)
print(char.review.pros.all)
print(char.build.weapon_recommendations.all.name)
print(char.gameplay.rotations)
print(char.gameplay.synergies)
mode = char.calculations.get("Default")
print(mode.damage_profile.raw_values)
print(mode.damage_profile.percentages)
print(char.snapshot_json())

# Always close explicitly in scripts.
chars.close()
```

`character.updates` mirrors the source page's Update Tracker:

```python
print(character.updates.review)              # Last review update
print(character.updates.build_calculations)  # Last major build/calcs update
print(character.updates.profile)             # Last profile update
print(character.updates.last_updated)        # Page's overall last-updated date
```

The context-manager form is still useful when cleanup must happen even if scraping
raises an exception:

```python
from sol3data import Characters

with Characters() as chars:
    print(chars.get("iuno").name)
```

## Browser and debugging options

`Characters` inherits from the public `BrowserSession`, so its lifecycle options
are available directly:

```python
from sol3data import Characters

chars = Characters(
    headless=False,                 # open a visible browser window
    slow_mo=250,                    # slow Playwright actions by 250 ms
    pause_on_open=True,             # open Playwright Inspector and wait for Resume
    trace_path="artifacts/trace.zip",
)
print(chars.get("iuno").name)
chars.close()
```

## Gameplay and teams

Gameplay content follows the same lazy property style as the other character
sections:

```python
gameplay = character.gameplay
print(gameplay.how_to_play)
print(gameplay.echo_timing)
print(gameplay.rotations)          # clean text by named rotation
print(gameplay.rotation_guides)    # steps and notes for each rotation
print(gameplay.additional_tips)
print(gameplay.synergies.dps)      # main DPS recommendations, role-aware
print(gameplay.synergies.sub_dps)  # sub-DPS / secondary damage dealers
print(gameplay.synergies.supports) # healers and supports
print(gameplay.team_compositions)  # example teams keyed from 1
```

Characters without a particular guide section return an empty string or mapping.

## Calculations

The calculation API has one canonical access rule: named data uses `.get(name)`
and sequence data uses `.get(sequence)`. Discovery uses `.names`; iteration uses
the collection itself. The old duplicate aliases were removed so the same value
does not have multiple competing access paths.

All public collection `.get(...)` methods have concrete generic return types, so
editor and REPL completion continues through chained calls:

```python
character.calculations.modes.get("Electro Flare").sequence_damage.get(0).damage
character.calculations.modes.get("Electro Flare").calculation_information.get("Rover (Electro)").weapon
```

Calculation modes expose their visible names for discovery:

```python
print(character.calculations.mode_names)

for mode in character.calculations:
    print(mode.name)
    print(character.calculations.additional_information)
    for teammate in mode.calculation_information:
        print(teammate.character, teammate.weapon, teammate.echo_set, teammate.main_echo)
    print(mode.rotation_time)
    print(mode.team_build.all)
    print(mode.damage_profile.raw_values)
    print(mode.damage_profile.percentages)

    for scenario in mode.scenarios.values():
        print(scenario.name)
        print(scenario.rotation_time)
        print(scenario.get(0))
        print(scenario.get(6))
```

For characters with only one calculation mode, use
`character.calculations.mode` directly. For multi-mode characters, use
`character.calculations.modes.get("Unison")` or
`character.calculations.get("Electro Flare")`. Both forms use the same
case-insensitive string lookup.

Use `.get(...)` for individual entries rather than indexing:

```python
mode = character.calculations.modes.get("Unison")
scenario = mode.get(1)
heavy_raw = scenario.damage_profile.get("Heavy")
heavy_share = scenario.damage_profile.get_percentage("Heavy")
build_entry = mode.team_build.get(1)
```

The damage profile exposes only attack types that contribute a non-zero value
in the site's profile, together with each one's raw total and percentage of the
profile total:

```python
profile = mode.damage_profile
print(profile.raw_values)       # {"Basic": "69,828", "Heavy": "2,052,386", ...}
print(profile.percentages)      # {"Basic": "2.61%", "Heavy": "76.52%", ...}
print(profile.total)
```

The percentages answer questions such as “what share of this rotation is Heavy
damage?” They are calculated from the displayed table totals, not from the
character's in-game ATK stat. The visual pie chart itself is not reimplemented,
since its table is the stable machine-readable representation.

`pause_on_open=True` uses Playwright's Inspector. It opens a visible browser
and an inspector window, pauses after navigation, and waits for you to press
Resume. This is useful for watching selectors and manually inspecting the
page. It requires `headless=False`; it is separate from `devtools=True`, which
opens Chromium DevTools without pausing execution.

## What's implemented

- `Characters` — character pages
  - `name`, `introduction`, `role`
  - `kit` — Kit tab
    - `skills` — active / passive / concerto skills with multipliers
    - `resonance_chain` — all 6 sequence nodes
    - `upgrade_materials` — material requirements (ascension, skill upgrades, etc.)
  - `review` — Review tab
    - `pros` & `cons`
    - `full_review`
    - `ratings` — tier list and value tier list, plus `available_roles` to check which roles have ratings
  - `build` — Build tab
    - `weapon_recommendations` — recommended weapons, usage %, and write-ups
    - `echo_recommendations` — recommended echo sets, rank, and write-ups
    - `echo_stats` — recommended main stats per cost slot, plus substat priority
    - `endgame_stats` — recommended endgame stat targets
    - `skill_priority` — skill priority order per role
  - `gameplay` — Gameplay and Teams tab
    - normalized how-to-play text, Echo timing, rotation guides, and tips
    - role-aware `dps`, `sub_dps`, and `supports` synergy groups
    - example team compositions
  - `calculations` — Calculations tab
    - named calculation mode discovery and lookup
    - team build entries, scenarios, raw damage profiles, and percentages
    - S0-S6 sequence damage access through `.get(...)` or named properties
  - `snapshot()` / `snapshot_json()` — complete JSON-safe character data for
    local AI agents, with requested sections and source metadata
  - shared normalization for names, slugs, mode lookup, and role names
  - session page caching and explicit cache invalidation with
    `characters.clear_cache()`

## What's coming

- Weapons
- Echoes
- Teams
- probably more idk

## Notes

- `Characters` starts lazily on the first request. Use `.close()` in scripts, or a `with` block for automatic cleanup.
- One `Characters` session reuses its browser and cached character pages. Run all
  reads inside one session and close it once at the end; a `with` block does this
  automatically.
- Gameplay, teams, and calculations are loaded asynchronously by the source
  site. The API waits for those panels to finish loading before returning
  parsed data, including when they are requested through `snapshot()`.
- Calculation explanations and results are separated:
  - `character.calculations.additional_information` is the site's global
    explanation of DMG/DPS simulations.
  - `mode.calculation_information` is the calculation buff team. Iterate it
    to inspect each character, weapon, Echo set, and main Echo.
  - `mode.rotation_time` gives the primary rotation duration.
  - `mode.sequence_damage.get(0)` through `.get(6)` returns S0-S6 damage,
    DPS, and relative sequence percentage.

```python
mode = character.calculations.modes.get("Unison")
s0 = mode.sequence_damage.get(0)
print(s0.damage, s0.dps, s0.percentage)
print(mode.rotation_time)
for teammate in mode.calculation_information:
    print(teammate.character, teammate.weapon, teammate.echo_set, teammate.main_echo)
```
- `character.snapshot()` returns a JSON-safe dictionary. Select sections with
  `character.snapshot(("identity", "gameplay", "calculations"))`, or use
  `character.snapshot_json()` for direct model input.
- Use `collection.find(...)` when an item is optional and should return `None`;
  use `collection.get(...)` when absence should raise a descriptive error.
- Individual collection entries should be accessed through their standardized
  `.get(...)` methods. For example, use `calculations.get("Unison")`,
  `mode.get(1)`, and `damage_profile.get("Heavy")`.
- Properties like `.all` return dictionaries populated with elements instead of requiring loops.
- Sections that don't exist for a given character (e.g. a role/rating a character doesn't have) raise `ValueError` rather than returning `None` — wrap in `try/except` when scraping many characters generically.
- I've also added docstrings everywhere, so your IDE should give you nice hints while coding!
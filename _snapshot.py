"""JSON-safe character snapshots for local agents and batch processing."""
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .characters.character import Character


class CharacterSnapshot:
    """Build a stable, JSON-safe representation from a character facade."""

    _sections = ("identity", "kit", "review", "build", "gameplay", "calculations")

    def __init__(self, character: "Character") -> None:
        self._character = character

    def build(self, include: tuple[str, ...] | str = "all") -> dict[str, Any]:
        selected = (
            self._sections
            if include == "all"
            else tuple(include) if not isinstance(include, str) else (include,)
        )
        unknown = set(selected) - set(self._sections)
        if unknown:
            raise ValueError(f"Unknown snapshot sections: {', '.join(sorted(unknown))}")
        result: dict[str, Any] = {
            "identity": self._identity(),
            "metadata": {
                "source": "prydwen.gg",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "sections_requested": list(selected),
                "sections_available": [],
                "sections_missing": [],
            },
        }
        for section in selected:
            if section == "identity":
                result["metadata"]["sections_available"].append(section)
                continue
            try:
                result[section] = getattr(self, f"_{section}")()
            except ValueError as error:
                result[section] = {"available": False, "reason": str(error)}
                result["metadata"]["sections_missing"].append(section)
            else:
                result["metadata"]["sections_available"].append(section)
        return result

    def _identity(self) -> dict[str, Any]:
        character = self._character
        updates = character.updates
        return {
            "name": character.name,
            "slug": character.slug,
            "url": character.url,
            "introduction": character.introduction,
            "roles": list(character.role.names),
            "updates": {
                "review": updates.review,
                "build_calculations": updates.build_calculations,
                "profile": updates.profile,
                "last_updated": updates.last_updated,
            },
        }

    def _gameplay(self) -> dict[str, Any]:
        gameplay = self._character.gameplay
        return {
            "how_to_play": gameplay.how_to_play,
            "echo_timing": gameplay.echo_timing,
            "rotations": gameplay.rotations,
            "rotation_guides": {
                name: {"name": guide.name, "steps": guide.steps, "notes": guide.notes}
                for name, guide in gameplay.rotation_guides.items()
            },
            "additional_tips": gameplay.additional_tips,
            "synergies": gameplay.synergies.all,
            "team_compositions": gameplay.team_compositions,
        }

    def _calculations(self) -> dict[str, Any]:
        calculations = self._character.calculations
        modes: dict[str, Any] = {}
        for mode in calculations:
            modes[mode.name] = {
                "calculation_information": [
                    {
                        "character": member.character,
                        "weapon": member.weapon,
                        "echo_set": member.echo_set,
                        "main_echo": member.main_echo,
                    }
                    for member in mode.calculation_information
                ],
                "rotation_time": mode.rotation_time,
                "team_build": mode.team_build.all,
                "damage_profile": {
                    "raw": mode.damage_profile.raw_values,
                    "percentages": mode.damage_profile.percentages,
                    "total": mode.damage_profile.total,
                },
                "scenarios": {
                    str(number): {
                        "name": scenario.name,
                        "rotation_time": scenario.rotation_time,
                        "sequence_damage": {
                            str(level): {
                                "damage": value.damage,
                                "dps": value.dps,
                                "percentage": value.percentage,
                            }
                            for level, value in scenario.sequence_damage.all.items()
                        },
                    }
                    for number, scenario in mode.scenarios.items()
                },
            }
        return {
            "additional_information": calculations.additional_information,
            "mode_names": list(calculations.mode_names),
            "modes": modes,
        }

    def _kit(self) -> dict[str, Any]:
        kit = self._character.kit
        active = kit.skills.active
        passive = kit.skills.passive
        concerto = kit.skills.concerto

        def skill_data(skill):
            return {
                "category": skill.category,
                "name": skill.name,
                "description": skill.description,
                "multipliers": skill.multipliers.all,
            }

        return {
            "active": {
                "basic_attack": skill_data(active.basic_attack),
                "resonance_skill": skill_data(active.resonance_skill),
                "resonance_liberation": skill_data(active.resonance_liberation),
            },
            "passive": {
                "forte_circuit": skill_data(passive.forte_circuit),
                "inherent_skill_1": skill_data(passive.inherent_skill_1),
                "inherent_skill_2": skill_data(passive.inherent_skill_2),
            },
            "concerto": {
                "intro_skill": skill_data(concerto.intro_skill),
                "outro_skill": skill_data(concerto.outro_skill),
            },
            "resonance_chain": {
                str(index): {
                    "sequence": node.sequence,
                    "name": node.name,
                    "description": node.description,
                }
                for index, node in kit.resonance_chain.all.items()
            },
        }

    def _review(self) -> dict[str, Any]:
        review = self._character.review
        return {
            "pros": review.pros.all,
            "cons": review.cons.all,
            "full_review": review.full_review,
            "available_roles": review.ratings.tier_list.available_roles,
        }

    def _build(self) -> dict[str, Any]:
        build = self._character.build
        return {
            "weapons": {
                str(index): {
                    "name": item.name,
                    "information": item.information,
                    "percentages": item.percentage.all,
                }
                for index, item in build.weapon_recommendations.all.items()
            },
            "echo_sets": {
                str(index): {
                    "name": item.name,
                    "percentage": item.percentage,
                    "information": item.information,
                }
                for index, item in build.echo_recommendations.all.items()
            },
            "echo_stats": build.echo_stats.all.stats,
            "endgame_stats": build.endgame_stats.lines,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.build()

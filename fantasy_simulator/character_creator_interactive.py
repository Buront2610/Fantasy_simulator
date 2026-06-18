"""Interactive character creation flow and prompts."""

from __future__ import annotations

from typing import Any, Dict, List, Protocol

from .character import Character
from .character_creator_builders import add_origin_history
from .character_creator_naming import GENDERS, random_name
from .character_personality import PERSONALITY_TRAITS, generate_personality, normalize_personality
from .i18n import tr


class _InteractiveInput(Protocol):
    def read_line(self, prompt: str = "") -> str:
        ...


class _InteractiveOutput(Protocol):
    def print_line(self, text: str = "") -> None:
        ...

    def print_separator(self, char: str = "=", width: int = 62) -> None:
        ...


class InteractiveContext(Protocol):
    inp: _InteractiveInput
    out: _InteractiveOutput


class _StdInput:
    def read_line(self, prompt: str = "") -> str:
        try:
            return input(prompt)
        except EOFError:
            return ""


class _StdOutput:
    def print_line(self, text: str = "") -> None:
        print(text)

    def print_separator(self, char: str = "=", width: int = 62) -> None:
        print(char * width)


class _StdInteractiveContext:
    inp: _InteractiveInput
    out: _InteractiveOutput

    def __init__(self) -> None:
        self.inp = _StdInput()
        self.out = _StdOutput()


def _default_interactive_ctx(ctx: InteractiveContext | None) -> InteractiveContext:
    if ctx is not None:
        return ctx
    return _StdInteractiveContext()


class CharacterCreatorInteractiveMixin:
    naming_rules: Any

    def _require_race_and_job_entries(
        self,
    ) -> tuple[List[tuple[str, str, Dict[str, int]]], List[tuple[str, str, List[str]]]]:
        raise NotImplementedError

    def create_interactive(self, ctx: InteractiveContext | None = None) -> Character:
        ctx = _default_interactive_ctx(ctx)
        out = ctx.out

        out.print_line()
        out.print_separator("=", 50)
        out.print_line(f"  {tr('interactive_character_creation')}")
        out.print_separator("=", 50)

        name = self._prompt(
            tr("enter_character_name"),
            default=random_name("Non-binary", self.naming_rules),
            ctx=ctx,
        )
        gender = self._prompt_choice(tr("choose_gender"), GENDERS, default="Non-binary", ctx=ctx)

        race_entries, job_entries = self._require_race_and_job_entries()
        race_names = [race[0] for race in race_entries]
        out.print_line(f"\n  {tr('available_races')}:")
        for i, (race_name, race_desc, _bonuses) in enumerate(race_entries, 1):
            out.print_line(f"  {i}. {race_name:12s} - {race_desc[:60]}...")
        race = self._prompt_choice(tr("choose_race"), race_names, default=race_names[0], ctx=ctx)

        job_names = [job[0] for job in job_entries]
        out.print_line(f"\n  {tr('available_jobs')}:")
        for i, (job_name, job_desc, _skills) in enumerate(job_entries, 1):
            out.print_line(f"  {i}. {job_name:12s} - {job_desc[:60]}...")
        job = self._prompt_choice(tr("choose_job"), job_names, default=job_names[0], ctx=ctx)

        age_str = self._prompt(tr("enter_starting_age"), default="20", ctx=ctx)
        try:
            age = max(15, min(80, int(age_str)))
        except ValueError:
            age = 20

        out.print_line(f"\n  {tr('stat_distribution_info')}")
        out.print_line(f"  {tr('accept_default_stats')}")
        stats = self._allocate_stats(ctx=ctx)

        race_bonuses = next((entry[2] for entry in race_entries if entry[0] == race), {})
        for stat, bonus in race_bonuses.items():
            if stat in stats:
                stats[stat] = Character._clamp(stats[stat] + bonus)

        job_skills = next((entry[2] for entry in job_entries if entry[0] == job), [])
        skills = {skill: 1 for skill in job_skills}

        personality = self._allocate_personality(ctx=ctx)

        char = Character(
            name=name,
            age=age,
            gender=gender,
            race=race,
            job=job,
            skills=skills,
            personality=personality,
            strength=stats["strength"],
            intelligence=stats["intelligence"],
            dexterity=stats["dexterity"],
            wisdom=stats["wisdom"],
            charisma=stats["charisma"],
            constitution=stats["constitution"],
        )
        add_origin_history(char, founder_background=True)
        out.print_line(f"\n  {tr('character_created')}")
        out.print_line(char.stat_block())
        return char

    @staticmethod
    def _prompt(message: str, default: str = "", ctx: InteractiveContext | None = None) -> str:
        ctx = _default_interactive_ctx(ctx)
        display = f"  > {message}"
        if default:
            display += f" [{default}]"
        display += ": "
        raw = ctx.inp.read_line(display).strip()
        return raw if raw else default

    @staticmethod
    def _prompt_choice(
        message: str,
        choices: List[str],
        default: str,
        ctx: InteractiveContext | None = None,
    ) -> str:
        ctx = _default_interactive_ctx(ctx)
        display = f"  > {message} ({'/'.join(choices)}) [{default}]: "
        while True:
            raw = ctx.inp.read_line(display).strip()
            if not raw:
                return default
            if raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < len(choices):
                    return choices[idx]
            matches = [choice for choice in choices if choice.lower().startswith(raw.lower())]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                ctx.out.print_line(f"  {tr('ambiguous_choice', matches=', '.join(matches))}")
            else:
                ctx.out.print_line(f"  {tr('invalid_options', choices=', '.join(choices))}")

    @staticmethod
    def _allocate_stats(ctx: InteractiveContext | None = None) -> Dict[str, int]:
        ctx = _default_interactive_ctx(ctx)
        stat_names = ["strength", "intelligence", "dexterity", "wisdom", "charisma", "constitution"]
        defaults = {stat: 10 for stat in stat_names}
        extra_points = 60

        raw = ctx.inp.read_line(f"  > {tr('manually_distribute_stats')}: ").strip().lower()
        if raw != "y":
            return defaults

        allocated: Dict[str, int] = dict(defaults)
        for stat in stat_names:
            while True:
                spent_extra = sum(value - 10 for value in allocated.values())
                left_extra = extra_points - spent_extra
                max_allowed = min(40, 10 + left_extra)
                raw_val = ctx.inp.read_line(
                    f"  > {stat.capitalize():15s} (10-{max_allowed}, {left_extra} pts left): "
                ).strip()
                if not raw_val:
                    val = 10
                else:
                    try:
                        val = int(raw_val)
                    except ValueError:
                        ctx.out.print_line(f"  {tr('please_enter_number')}")
                        continue
                if val < 10 or val > max_allowed:
                    ctx.out.print_line(f"  {tr('must_be_between', lo=10, hi=max_allowed)}")
                    continue
                allocated[stat] = val
                break
        return allocated

    @staticmethod
    def _allocate_personality(ctx: InteractiveContext | None = None) -> Dict[str, int]:
        ctx = _default_interactive_ctx(ctx)
        raw = ctx.inp.read_line(f"  > {tr('customize_personality')}: ").strip().lower()
        if raw != "y":
            return generate_personality()

        values: Dict[str, int] = {}
        for trait in PERSONALITY_TRAITS:
            label = tr(f"personality_trait_name_{trait}")
            while True:
                raw_val = ctx.inp.read_line(
                    f"  > {label:15s} (0-100, default 50): "
                ).strip()
                if not raw_val:
                    values[trait] = 50
                    break
                try:
                    values[trait] = int(raw_val)
                except ValueError:
                    ctx.out.print_line(f"  {tr('please_enter_number')}")
                    continue
                break
        return normalize_personality(values)

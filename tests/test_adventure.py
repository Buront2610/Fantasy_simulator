"""
tests/test_adventure.py - Unit tests for adventure progression.
"""

import random

from fantasy_simulator.adventure import (
    AdventureChoice,
    AdventureRun,
    CHOICE_PROCEED_CAUTIOUSLY,
    CHOICE_PRESS_ON,
    CHOICE_RETREAT,
    CHOICE_WITHDRAW,
    POLICY_CAUTIOUS,
    POLICY_ASSAULT,
    POLICY_SWIFT,
    POLICY_TREASURE,
    POLICY_RESCUE,
    RETREAT_ON_SERIOUS,
    RETREAT_ON_SUPPLY,
    RETREAT_ON_TROPHY,
    RETREAT_NEVER,
    SUPPLY_FULL,
    SUPPLY_LOW,
    SUPPLY_CRITICAL,
    ALL_POLICIES,
    create_adventure_run,
    select_party_policy,
)
from fantasy_simulator.character import Character
from fantasy_simulator.i18n import set_locale
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.world import World


class FakeRng:
    def __init__(self, random_values, choice_value=None):
        self.random_values = list(random_values)
        self.choice_value = choice_value

    def random(self):
        if self.random_values:
            return self.random_values.pop(0)
        return 0.99

    def choice(self, options):
        if self.choice_value is not None and self.choice_value in options:
            return self.choice_value
        return options[0]

    def randint(self, lo, hi):
        return lo

    def choices(self, population, weights=None, k=1):
        return [population[0]] * k

    def sample(self, population, k):
        return list(population[:k])


def _make_character(name="Aldric") -> Character:
    return Character(
        name=name,
        age=25,
        gender="Male",
        race="Human",
        job="Warrior",
        strength=60,
        dexterity=50,
        constitution=55,
        location_id="loc_aethoria_capital",
    )


def test_adventure_run_round_trip_serialization():
    run = AdventureRun(
        character_id="hero1",
        character_name="Aldric",
        origin="loc_aethoria_capital",
        destination="loc_thornwood",
        year_started=1000,
        state="waiting_for_choice",
        injury_status="injured",
        loot_summary=["an ancient relic"],
    )
    run.summary_log.append("Aldric reached the woods.")
    run.detail_log.append("Aldric paused at the ruins entrance.")
    run.pending_choice = AdventureChoice(
        prompt="Press onward?",
        options=["press_on", "retreat"],
        default_option="retreat",
        context="depth",
    )
    payload = run.to_dict()
    restored = AdventureRun.from_dict(payload)

    assert restored.character_name == "Aldric"
    assert restored.state == "waiting_for_choice"
    assert restored.injury_status == "injured"
    assert restored.loot_summary == ["an ancient relic"]
    assert restored.summary_log == ["Aldric reached the woods."]
    assert restored.pending_choice is not None
    assert restored.pending_choice.default_option == "retreat"


def test_travel_step_can_enter_waiting_for_choice_state():
    world = World()
    char = _make_character()
    world.add_character(char)
    run = create_adventure_run(char, world, rng=FakeRng([0.9]))

    summaries = run.step(char, world, rng=FakeRng([0.10]))

    assert summaries
    assert run.state == "waiting_for_choice"
    assert run.pending_choice is not None
    assert len(run.pending_choice.options) >= 2
    assert set(run.pending_choice.options) <= {
        CHOICE_PRESS_ON,
        CHOICE_PROCEED_CAUTIOUSLY,
        CHOICE_RETREAT,
        CHOICE_WITHDRAW,
    }


def test_waiting_choice_defaults_automatically_on_next_step():
    world = World()
    char = _make_character()
    world.add_character(char)
    run = create_adventure_run(char, world, rng=FakeRng([0.9]))
    run.step(char, world, rng=FakeRng([0.10]))

    summaries = run.step(char, world, rng=FakeRng([0.90, 0.90]))

    assert summaries == []
    assert run.pending_choice is None
    assert run.state == "exploring"


def test_injury_outcome_uses_injury_field_without_mutating_constitution():
    world = World()
    char = _make_character()
    world.add_character(char)
    run = AdventureRun(
        character_id=char.char_id,
        character_name=char.name,
        origin=char.location_id,
        destination="loc_thornwood",
        year_started=world.year,
        state="exploring",
    )
    char.active_adventure_id = run.adventure_id
    before_constitution = char.constitution

    run.step(char, world, rng=FakeRng([0.10]))
    summaries = run.step(char, world, rng=FakeRng([0.90]))

    assert summaries
    assert run.outcome == "injury"
    assert char.injury_status == "injured"
    assert char.constitution == before_constitution


def test_simulator_integrates_adventures_into_normal_year_loop(monkeypatch):
    world = World()
    char = _make_character()
    world.add_character(char)
    sim = Simulator(world, events_per_year=0, adventure_steps_per_year=4, seed=1)

    # exploration now includes a loot-probability roll; provide low roll to ensure discovery
    sim.rng = FakeRng([0.9, 0.0, 0.9, 0.3, 0.1, 0.9])

    sim._run_year()

    assert len(world.completed_adventures) == 1
    run = world.completed_adventures[0]
    assert run.outcome == "safe_return"
    assert any("set out" in entry.lower() for entry in world.event_log)
    assert sim.get_adventure_summaries()


def test_pending_choice_persists_until_later_year(monkeypatch):
    world = World()
    char = _make_character()
    world.add_character(char)
    sim = Simulator(world, events_per_year=0, adventure_steps_per_year=4, seed=1)

    sim.rng = FakeRng([0.9, 0.0, 0.10, 0.9, 0.1, 0.9, 0.9])

    sim._run_year()

    assert len(world.active_adventures) == 1
    run = world.active_adventures[0]
    assert run.pending_choice is not None
    assert run.state == "waiting_for_choice"

    sim._run_year()

    assert world.active_adventures == []
    assert len(world.completed_adventures) == 1
    assert world.completed_adventures[0].outcome in {"safe_return", "retreat"}


def test_choice_resolution_survives_locale_change():
    world = World()
    char = _make_character()
    world.add_character(char)
    run = create_adventure_run(char, world, rng=FakeRng([0.9]))
    run.step(char, world, rng=FakeRng([0.10]))

    set_locale("ja")
    assert run.pending_choice is not None
    assert run.pending_choice.default_option == CHOICE_PROCEED_CAUTIOUSLY

    set_locale("en")
    summaries = run.resolve_choice(world, char, option=CHOICE_RETREAT)

    assert summaries
    assert run.state == "returning"
    assert run.pending_choice is None


def test_adventure_id_generation_uses_separate_rng():
    world = World()
    char = _make_character()
    world.add_character(char)

    gameplay_rng = random.Random(123)
    gameplay_clone = random.Random()
    gameplay_clone.setstate(gameplay_rng.getstate())
    id_rng = random.Random(999)

    neighbors = world.get_neighboring_locations(char.location_id)
    risky = [loc for loc in neighbors if loc.region_type in ("forest", "mountain", "dungeon")]
    if not risky:
        risky = [
            loc for loc in world.grid.values()
            if loc.region_type in ("forest", "mountain", "dungeon")
        ]
    _ = gameplay_clone.choice(risky)

    create_adventure_run(char, world, rng=gameplay_rng, id_rng=id_rng)

    assert gameplay_rng.getstate() == gameplay_clone.getstate()


def test_adventure_death_clears_spouse_on_survivor():
    """When a dying character dies during an adventure, the surviving spouse's
    spouse_id must be cleared and the spouse must receive a history entry.

    With death staging (design §8), only already-dying characters die
    instantly in the 0.18-0.24 range; others worsen injury instead.
    """
    world = World()
    hero = _make_character("Hero")
    spouse = _make_character("Spouse")
    world.add_character(hero)
    world.add_character(spouse)

    hero.spouse_id = spouse.char_id
    spouse.spouse_id = hero.char_id
    # Hero must already be dying for instant death
    hero.injury_status = "dying"

    sim = Simulator(world, events_per_year=0, adventure_steps_per_year=4, seed=1)

    run = AdventureRun(
        character_id=hero.char_id,
        character_name=hero.name,
        origin=hero.location_id,
        destination="loc_thornwood",
        year_started=world.year,
        state="exploring",
        policy=POLICY_ASSAULT,
    )
    hero.active_adventure_id = run.adventure_id
    world.add_adventure(run)

    # Roll in (injury_chance, critical_chance): causes death for already-dying target
    run.step(hero, world, rng=FakeRng([0.24]))

    assert not hero.alive
    assert run.outcome == "death"

    # Simulate what the simulator does after a step kills the character
    sim.event_system.handle_death_side_effects(hero, world)

    assert spouse.spouse_id is None
    assert any("Hero" in h for h in spouse.history)


# ---------------------------------------------------------------------------
# PR-E: Party adventure tests
# ---------------------------------------------------------------------------

def _make_party_run(leader, members, world, policy=POLICY_CAUTIOUS, retreat_rule=RETREAT_ON_SERIOUS):
    """Helper: create a party AdventureRun linked to members."""
    run = AdventureRun(
        character_id=leader.char_id,
        character_name=leader.name,
        origin=leader.location_id,
        destination="loc_thornwood",
        year_started=world.year,
        state="exploring",
        member_ids=[m.char_id for m in members],
        policy=policy,
        retreat_rule=retreat_rule,
        danger_level=50,
    )
    for m in members:
        m.active_adventure_id = run.adventure_id
    world.add_adventure(run)
    return run


def test_party_adventure_round_trip_serialization():
    """Party fields survive to_dict / from_dict round-trip."""
    run = AdventureRun(
        character_id="c1",
        character_name="Aldric",
        origin="loc_aethoria_capital",
        destination="loc_thornwood",
        year_started=1000,
        member_ids=["c1", "c2", "c3"],
        party_id="party_abc",
        policy=POLICY_TREASURE,
        retreat_rule=RETREAT_ON_TROPHY,
        supply_state=SUPPLY_LOW,
        danger_level=75,
    )
    payload = run.to_dict()
    restored = AdventureRun.from_dict(payload)

    assert restored.member_ids == ["c1", "c2", "c3"]
    assert restored.party_id == "party_abc"
    assert restored.policy == POLICY_TREASURE
    assert restored.retreat_rule == RETREAT_ON_TROPHY
    assert restored.supply_state == SUPPLY_LOW
    assert restored.danger_level == 75
    assert restored.is_party is True


def test_party_backward_compat_no_member_ids():
    """from_dict with no member_ids (pre-PR-E save) defaults to [character_id]."""
    data = {
        "character_id": "hero1",
        "character_name": "Aldric",
        "origin": "loc_aethoria_capital",
        "destination": "loc_thornwood",
        "year_started": 1000,
        # no member_ids key (old save format)
    }
    run = AdventureRun.from_dict(data)
    assert run.member_ids == ["hero1"]
    assert run.is_party is False
    assert run.policy == POLICY_CAUTIOUS
    assert run.retreat_rule == RETREAT_ON_SERIOUS


def test_is_party_property():
    """is_party is True only when len(member_ids) > 1."""
    solo = AdventureRun(
        character_id="c1", character_name="A",
        origin="loc_aethoria_capital", destination="loc_thornwood",
        year_started=1000, member_ids=["c1"],
    )
    party = AdventureRun(
        character_id="c1", character_name="A",
        origin="loc_aethoria_capital", destination="loc_thornwood",
        year_started=1000, member_ids=["c1", "c2"],
    )
    empty = AdventureRun(
        character_id="c1", character_name="A",
        origin="loc_aethoria_capital", destination="loc_thornwood",
        year_started=1000,
    )
    assert solo.is_party is False
    assert party.is_party is True
    assert empty.is_party is False


def test_combat_score_scales_injury_chance():
    """High STR+CON lowers injury_chance; low STR+CON raises it.

    Design §9.6: STR/CON → 正面戦闘・耐久.
    """
    strong_char = Character(
        name="Tank", age=25, gender="Male", race="Human", job="Warrior",
        strength=90, constitution=90, dexterity=50, wisdom=50,
        location_id="loc_aethoria_capital",
    )
    weak_char = Character(
        name="Scholar", age=25, gender="Female", race="Human", job="Mage",
        strength=15, constitution=15, dexterity=50, wisdom=50,
        location_id="loc_aethoria_capital",
    )
    run = AdventureRun(
        character_id="x", character_name="X",
        origin="loc_aethoria_capital", destination="loc_thornwood",
        year_started=1000, danger_level=50,
    )
    strong_chance = run._compute_injury_chance([strong_char])
    weak_chance = run._compute_injury_chance([weak_char])

    assert strong_chance < weak_chance, (
        f"Expected strong_chance ({strong_chance:.3f}) < weak_chance ({weak_chance:.3f})"
    )
    # Sanity bounds: must stay within clamped range [0.04, 0.22]
    assert 0.04 <= strong_chance <= 0.22
    assert 0.04 <= weak_chance <= 0.22


def test_danger_level_scales_injury_chance():
    """Higher danger_level raises injury_chance; lower reduces it.

    Design §9.6: location danger affects risk.
    """
    char = _make_character()
    run_safe = AdventureRun(
        character_id="x", character_name="X",
        origin="loc_aethoria_capital", destination="loc_thornwood",
        year_started=1000, danger_level=10,
    )
    run_dangerous = AdventureRun(
        character_id="x", character_name="X",
        origin="loc_aethoria_capital", destination="loc_thornwood",
        year_started=1000, danger_level=90,
    )
    safe_chance = run_safe._compute_injury_chance([char])
    dangerous_chance = run_dangerous._compute_injury_chance([char])

    assert safe_chance < dangerous_chance, (
        f"Expected safe ({safe_chance:.3f}) < dangerous ({dangerous_chance:.3f})"
    )


def test_policy_modifies_injury_chance():
    """Cautious policy should be safer than assault with same members/danger."""
    char = _make_character()
    cautious_run = AdventureRun(
        character_id="x", character_name="X",
        origin="loc_aethoria_capital", destination="loc_thornwood",
        year_started=1000, danger_level=50, policy=POLICY_CAUTIOUS,
    )
    assault_run = AdventureRun(
        character_id="x", character_name="X",
        origin="loc_aethoria_capital", destination="loc_thornwood",
        year_started=1000, danger_level=50, policy=POLICY_ASSAULT,
    )
    assert cautious_run._compute_injury_chance([char]) < assault_run._compute_injury_chance([char])


def test_policy_modifies_loot_chance():
    """Treasure policy should find loot more often than rescue with same lore score."""
    char = _make_character()
    treasure_run = AdventureRun(
        character_id="x", character_name="X",
        origin="loc_aethoria_capital", destination="loc_thornwood",
        year_started=1000, policy=POLICY_TREASURE,
    )
    rescue_run = AdventureRun(
        character_id="x", character_name="X",
        origin="loc_aethoria_capital", destination="loc_thornwood",
        year_started=1000, policy=POLICY_RESCUE,
    )
    assert treasure_run._compute_loot_chance([char]) > rescue_run._compute_loot_chance([char])


def test_policy_modifies_supply_degradation_rate():
    """Assault should deplete supply faster than swift under same random roll."""
    assault_run = AdventureRun(
        character_id="x",
        character_name="X",
        origin="loc_aethoria_capital",
        destination="loc_thornwood",
        year_started=1000,
        policy=POLICY_ASSAULT,
        supply_state=SUPPLY_FULL,
    )
    swift_run = AdventureRun(
        character_id="x",
        character_name="X",
        origin="loc_aethoria_capital",
        destination="loc_thornwood",
        year_started=1000,
        policy=POLICY_SWIFT,
        supply_state=SUPPLY_FULL,
    )
    # Roll 0.16: assault threshold = 0.1875 (degrades), swift threshold = 0.105 (stays full)
    assault_run._tick_supply(FakeRng([0.16]))
    swift_run._tick_supply(FakeRng([0.16]))

    assert assault_run.supply_state == SUPPLY_LOW
    assert swift_run.supply_state == SUPPLY_FULL


def test_policy_changes_pending_choice_defaults():
    """Choice defaults should vary by policy and context."""
    world = World()
    char = _make_character()
    world.add_character(char)

    cautious_run = create_adventure_run(char, world, rng=FakeRng([0.99]))
    cautious_run.policy = POLICY_CAUTIOUS
    cautious_run.state = "traveling"
    cautious_run.step(char, world, rng=FakeRng([0.10]))
    assert cautious_run.pending_choice is not None
    assert cautious_run.pending_choice.default_option == CHOICE_PROCEED_CAUTIOUSLY

    assault_run = create_adventure_run(char, world, rng=FakeRng([0.99]))
    assault_run.policy = POLICY_ASSAULT
    assault_run.state = "traveling"
    assault_run.step(char, world, rng=FakeRng([0.10]))
    assert assault_run.pending_choice is not None
    assert assault_run.pending_choice.default_option == CHOICE_PRESS_ON

    # depth context defaults
    cautious_run.pending_choice = None
    cautious_run.state = "exploring"
    cautious_run.step(char, world, rng=FakeRng([0.99, 0.01, 0.10]))
    assert cautious_run.pending_choice is not None
    assert cautious_run.pending_choice.context == "depth"
    assert cautious_run.pending_choice.default_option == CHOICE_WITHDRAW

    assault_run.pending_choice = None
    assault_run.state = "exploring"
    assault_run.step(char, world, rng=FakeRng([0.99, 0.01, 0.10]))
    assert assault_run.pending_choice is not None
    assert assault_run.pending_choice.context == "depth"
    assert assault_run.pending_choice.default_option == CHOICE_PRESS_ON


def test_party_ability_score_averages():
    """Party ability scores are averaged across all living members."""
    char_a = Character(
        name="A", age=25, gender="Male", race="Human", job="Warrior",
        strength=80, constitution=80, dexterity=50, wisdom=50, intelligence=50,
        location_id="loc_aethoria_capital",
    )
    char_b = Character(
        name="B", age=25, gender="Female", race="Human", job="Mage",
        strength=20, constitution=20, dexterity=50, wisdom=50, intelligence=80,
        location_id="loc_aethoria_capital",
    )
    run = AdventureRun(
        character_id="x", character_name="X",
        origin="loc_aethoria_capital", destination="loc_thornwood",
        year_started=1000,
    )
    combat = run._combat_score([char_a, char_b])
    lore = run._lore_score([char_a, char_b])

    # combat = avg of (STR+CON)/2: (80+80)/2=80, (20+20)/2=20 → avg=50
    assert abs(combat - 50.0) < 0.01
    # lore = avg INT: (50 + 80) / 2 = 65
    assert abs(lore - 65.0) < 0.01


def test_retreat_on_serious_triggers_when_member_serious():
    """RETREAT_ON_SERIOUS returns True if any member is serious or dying."""
    healthy = _make_character("Healthy")
    serious = Character(
        name="Serious", age=30, gender="Female", race="Human", job="Warrior",
        location_id="loc_aethoria_capital", injury_status="serious",
    )
    run = AdventureRun(
        character_id="x", character_name="X",
        origin="loc_aethoria_capital", destination="loc_thornwood",
        year_started=1000, retreat_rule=RETREAT_ON_SERIOUS,
    )
    assert run._should_auto_retreat([healthy]) is False
    assert run._should_auto_retreat([healthy, serious]) is True


def test_retreat_on_trophy_triggers_when_loot_present():
    """RETREAT_ON_TROPHY returns True once any loot is in loot_summary."""
    char = _make_character()
    run = AdventureRun(
        character_id="x", character_name="X",
        origin="loc_aethoria_capital", destination="loc_thornwood",
        year_started=1000, retreat_rule=RETREAT_ON_TROPHY,
    )
    assert run._should_auto_retreat([char]) is False
    run.loot_summary.append("an ancient relic")
    assert run._should_auto_retreat([char]) is True


def test_retreat_on_supply_triggers_when_critical():
    """RETREAT_ON_SUPPLY returns True when supply_state is critical."""
    char = _make_character()
    run = AdventureRun(
        character_id="x", character_name="X",
        origin="loc_aethoria_capital", destination="loc_thornwood",
        year_started=1000, retreat_rule=RETREAT_ON_SUPPLY,
        supply_state=SUPPLY_FULL,
    )
    assert run._should_auto_retreat([char]) is False
    run.supply_state = SUPPLY_CRITICAL
    assert run._should_auto_retreat([char]) is True


def test_retreat_never_never_triggers():
    """RETREAT_NEVER never auto-retreats regardless of conditions."""
    char = _make_character()
    char.injury_status = "dying"
    run = AdventureRun(
        character_id="x", character_name="X",
        origin="loc_aethoria_capital", destination="loc_thornwood",
        year_started=1000, retreat_rule=RETREAT_NEVER,
        supply_state=SUPPLY_CRITICAL,
    )
    run.loot_summary.append("relic")
    assert run._should_auto_retreat([char]) is False


def test_party_auto_retreat_on_serious_member(monkeypatch):
    """A party adventure auto-retreats when a member reaches 'serious' during exploring.

    Design §9.5: retreat if someone is serious or dying.
    """
    world = World()
    leader = _make_character("Aldric")
    companion = _make_character("Lysara")
    world.add_character(leader)
    world.add_character(companion)

    companion.injury_status = "serious"  # companion is already serious

    run = _make_party_run(
        leader, [leader, companion], world,
        policy=POLICY_CAUTIOUS, retreat_rule=RETREAT_ON_SERIOUS,
    )

    # No injury roll needed — auto-retreat should trigger immediately
    summaries = run.step(leader, world, rng=FakeRng([0.99, 0.99]))

    assert run.state == "returning", f"Expected returning, got {run.state}"
    assert summaries, "Expected at least one summary"
    assert any("retreated" in s.lower() or "撤退" in s for s in summaries)


def test_solo_run_ignores_retreat_rule_on_self_injury():
    """Solo run does NOT auto-retreat even when the solo char is dying.

    Auto-retreat is a party-only mechanic (design: leader-character alone
    cannot 'retreat as a party').  The existing injury/death roll handles it.
    """
    world = World()
    char = _make_character()
    char.injury_status = "dying"
    world.add_character(char)

    run = AdventureRun(
        character_id=char.char_id,
        character_name=char.name,
        origin=char.location_id,
        destination="loc_thornwood",
        year_started=world.year,
        state="exploring",
        member_ids=[char.char_id],   # solo = 1 member → is_party = False
        retreat_rule=RETREAT_ON_SERIOUS,
        policy=POLICY_ASSAULT,
    )
    char.active_adventure_id = run.adventure_id
    world.add_adventure(run)

    # Roll that lands in the critical zone (death for dying char)
    # With STR=60, CON=55 (from _make_character) and danger_level=50:
    # Use a roll in (injury_chance, critical_chance) for assault policy.
    run.step(char, world, rng=FakeRng([0.24]))

    # Should die (not auto-retreat) since is_party = False
    assert not char.alive
    assert run.outcome == "death"


def test_party_member_cleanup_on_adventure_resolve():
    """When party adventure resolves, all non-leader members have active_adventure_id cleared."""
    world = World()
    leader = _make_character("Aldric")
    companion = _make_character("Lysara")
    world.add_character(leader)
    world.add_character(companion)

    run = _make_party_run(leader, [leader, companion], world)
    run.state = "returning"

    # Advance through the returning step
    run.step(leader, world, rng=FakeRng([0.99]))

    assert run.is_resolved
    assert leader.active_adventure_id is None
    assert companion.active_adventure_id is None


def test_party_injury_can_target_companion():
    """Injury may hit non-leader members, not only the leader."""
    world = World()
    leader = _make_character("Aldric")
    companion = _make_character("Lysara")
    world.add_character(leader)
    world.add_character(companion)
    run = _make_party_run(leader, [leader, companion], world, policy=POLICY_ASSAULT)

    # Force injury branch and force injured target to companion.
    # First roll is supply tick (non-injury); second roll drives injury branch.
    run.step(leader, world, rng=FakeRng([0.99, 0.01], choice_value=companion))

    assert companion.injury_status in ("injured", "serious", "dying")
    assert leader.injury_status == "none"


def test_party_returning_applies_injury_to_actual_injured_member():
    """Companion injury must not be transferred to leader on return."""
    world = World()
    leader = _make_character("Aldric")
    companion = _make_character("Lysara")
    world.add_character(leader)
    world.add_character(companion)

    run = _make_party_run(leader, [leader, companion], world, policy=POLICY_ASSAULT)
    run.injury_status = "injured"
    run.injury_member_id = companion.char_id
    run.state = "returning"
    run.step(leader, world, rng=FakeRng([0.99]))

    assert companion.injury_status == "injured"
    assert leader.injury_status == "none"


def test_create_adventure_run_sets_member_ids():
    """create_adventure_run initialises member_ids to [char_id] for solo run."""
    world = World()
    char = _make_character()
    world.add_character(char)
    run = create_adventure_run(char, world, rng=FakeRng([0.99]))

    assert run.member_ids == [char.char_id]
    assert run.is_party is False


def test_select_party_policy_returns_valid_policy():
    """select_party_policy always returns a policy from ALL_POLICIES."""
    rng = FakeRng([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
    members = [_make_character("A"), _make_character("B")]
    for _ in range(10):
        policy = select_party_policy(members, rng)
        assert policy in ALL_POLICIES, f"Unexpected policy: {policy}"


def test_select_party_policy_wisdom_favours_cautious():
    """High-WIS party tends toward POLICY_CAUTIOUS more than POLICY_ASSAULT."""
    class FixedRng:
        def random(self):
            return 0.0   # always picks top-ranked policy

        def choice(self, options):
            return options[0]

    wise_party = [
        Character(
            name="A", age=25, gender="Male", race="Human", job="Mage",
            strength=20, constitution=20, dexterity=50, wisdom=90, intelligence=50,
            location_id="loc_aethoria_capital",
        )
    ]
    policy = select_party_policy(wise_party, FixedRng())
    # Wisdom scores highest for CAUTIOUS and RESCUE — should NOT be ASSAULT
    assert policy != POLICY_ASSAULT, f"Unexpected policy for high-WIS: {policy}"


def test_simulator_starts_party_adventure():
    """When multiple candidates exist, some adventures become party runs."""
    world = World()
    for i in range(6):
        c = _make_character(f"Hero{i}")
        world.add_character(c)
    sim = Simulator(world, events_per_year=0, adventure_steps_per_year=0, seed=42)

    # Force party formation by setting rng to always go party path
    class PartyForcedRng:
        """Always passes 25% gate and always picks party formation."""
        def __init__(self):
            self._calls = 0

        def random(self):
            self._calls += 1
            # Call 1: < 0.25 → proceed to adventure start
            # Call 2: < 0.30 → party formation
            if self._calls % 2 == 1:
                return 0.10   # < 0.25, proceed
            return 0.10       # < 0.30, form party

        def choice(self, options):
            return options[0]

        def sample(self, population, k):
            return list(population[:k])

        def choices(self, population, weights=None, k=1):
            return [population[0]] * k

        def randint(self, lo, hi):
            return lo

        def getrandbits(self, n):
            return 0

    sim.rng = PartyForcedRng()
    sim.id_rng = PartyForcedRng()
    sim._maybe_start_adventure()

    party_runs = [r for r in world.active_adventures if r.is_party]
    assert party_runs, "Expected at least one party adventure run"
    assert len(party_runs[0].member_ids) >= 2


def test_adventure_death_clears_spouse_via_simulator_integration():
    """Full integration: simulator's _advance_adventures handles spouse
    cleanup when a dying character's adventure step kills them.

    With death staging (design §8), character must be dying to die in
    the 0.18-0.24 roll range; otherwise injury worsens.
    """
    world = World()
    hero = _make_character("Hero")
    spouse = _make_character("Spouse")
    world.add_character(hero)
    world.add_character(spouse)

    hero.spouse_id = spouse.char_id
    spouse.spouse_id = hero.char_id
    # Hero must already be dying for instant death
    hero.injury_status = "dying"

    sim = Simulator(world, events_per_year=0, adventure_steps_per_year=1, seed=1)

    run = AdventureRun(
        character_id=hero.char_id,
        character_name=hero.name,
        origin=hero.location_id,
        destination="loc_thornwood",
        year_started=world.year,
        state="exploring",
        policy=POLICY_ASSAULT,
    )
    hero.active_adventure_id = run.adventure_id
    world.add_adventure(run)

    # Use a roll in (injury_chance, critical_chance): death for already-dying character.
    sim.rng = FakeRng([0.24])
    sim._advance_adventures()

    assert not hero.alive
    assert spouse.spouse_id is None
    assert any("Hero" in h for h in spouse.history)

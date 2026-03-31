"""Narrative/world-memory event kind constants."""

EVENT_KIND_ADVENTURE_DEATH = "adventure_death"
EVENT_KIND_BATTLE_FATAL = "battle_fatal"
EVENT_KIND_DEATH = "death"
EVENT_KIND_DISCOVERY = "discovery"
EVENT_KIND_RESCUE = "rescue"
EVENT_KIND_BETRAYAL = "betrayal"

EVENT_KINDS_FATAL = frozenset({
    EVENT_KIND_DEATH,
    EVENT_KIND_BATTLE_FATAL,
    EVENT_KIND_ADVENTURE_DEATH,
})

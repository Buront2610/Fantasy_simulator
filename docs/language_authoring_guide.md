# Language Authoring Guide

`fantasy_simulator/language/` is the single source of truth for generated language behavior.

## Responsibilities

- Static bundle data lives in `WorldDefinition.languages` and `language_communities`.
- Runtime drift lives in `language_runtime_states` and `language_evolution_history`.
- `World` owns persisted state, while `fantasy_simulator/world_language.py` coordinates yearly language updates and debug views.

## Community Fallback Contract

`LanguageEngine.resolve_language()` follows this order:

1. exact selector match
2. partial best match among the selectors you did provide
3. highest-priority `is_lingua_franca` community
4. the only defined language, when there is just one
5. otherwise `None`

Legacy `naming_rules` fallback is applied by higher-level callers, not by the
language engine itself.

Authoring implication: race-only, tribe-only, region-only, and mixed selectors
can all be used intentionally. Partial identities stay stable because the
engine now scores compatible communities instead of failing eagerly.

## Endonyms And Aliases

- `native_name` on a site seed is the author-written local name.
- Generated endonyms are system-generated local forms derived from the assigned language.
- World-memory aliases are player/history-facing nicknames created by simulation events.

Generated endonyms are not memory aliases and are stored separately on
`LocationState.generated_endonym`.

UI policy:

- Canonical name stays primary.
- Generated endonym is shown as a native-name cue.
- Memory aliases keep using `Known as`.
- Generated endonyms do not consume the memory-alias cap.

## Rule Order And Inheritance

Child languages inherit parent lexicon roots by evolving already-inherited forms forward into the child language.

Effective sound-change order is:

1. Legacy `sound_shifts`
2. Structured bundle `sound_change_rules`
3. Runtime `applied_rules`

Parent changes affect inherited vocabulary because the child derives from the parent's evolved lexicon, but child runtime rules are still applied in the child layer only.

## Inspiration Tags

`inspiration_tags` are flavor presets, not strict reconstructions of real languages. They are intended to bias phonological drift and naming feel, not to emulate a living language exactly.

## Cultures And Factions

`WorldDefinition.cultures` and `WorldDefinition.factions` are currently flat
authoring-name lists. Until a structured culture/faction schema lands, keep
entries conservative and align them with existing language communities,
site seeds, and location-state concepts such as `controlling_faction_id`.

For Aethoria, the first pass mirrors the established language/community map:
Aethic heartlands and lowlands, Quenic courts, Sindral woodland circles,
Khazic northern holds, frontier steppe clans, Dragonbone reaches, and coastal
mariner or sea-mage communities. Faction names should likewise be anchored to
existing seeded sites or professions rather than introducing new geopolitical
history ahead of PR-K.

## Debugging

Use `World.language_status()` when reviewing a generated language. The status payload is expected to include:

- lineage
- sample forms
- applied rules
- effective rules
- runtime-state summaries
- recent evolution records
- a flat `sound_shifts` summary
- `evolution_count`

For deeper debugging, pair it with:

- `World.language_evolution_records(language_key)`
- `World.describe_language_lineage(language_key)`
- serialized `language_evolution_history`
- serialized `language_runtime_states`

## Persistence

Save data may contain both `language_evolution_history` and
`language_runtime_states`.

- History is the canonical record.
- Runtime state is a cache derived from that history.
- Load rebuilds runtime state from history when history exists so deterministic
  restore behavior does not depend on whether cached runtime state was present.

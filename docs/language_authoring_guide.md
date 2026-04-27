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

Authoring policy:

- Add authored `native_name` values only for sites whose local form should be
  stable setting canon, such as capitals, major cities, sacred sites, or named
  regional landmarks.
- Match each authored form to the site's existing `language_key`; do not add or
  change language keys just to justify a local name.
- Keep uncertain or minor sites unset so the language engine can continue to
  provide generated endonyms.
- Treat `native_name` as display flavor only. Do not use it to rename
  `location_id`, canonical `name`, routes, save data, or schema fields.

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

## Phonological Feature Inventories

Language definitions may include optional feature lists such as
`front_vowels`, `back_vowels`, `liquid_consonants`, `nasal_consonants`,
`fricative_consonants`, and `stop_consonants`.

Authoring policy:

- Fill feature lists only from values already present in the same language's
  `vowels` or `consonants` inventory.
- Do not add base `vowels` or `consonants` just to support feature metadata on
  a child language; inherited inventories can remain implicit.
- Treat feature lists as descriptive authoring metadata unless a future rule
  explicitly consumes them.

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

## Glossary

`WorldDefinition.glossary` is an optional authoring list for stable setting
terms. It is bundle metadata only; it does not change save data, runtime world
state, generated language behavior, or canonical ids.

Each glossary entry currently supports:

- `term`: required display term.
- `definition`: optional short authoring note.
- `category`: optional broad grouping such as `era`, `history`, `magic`,
  `calendar`, or `language`.

Authoring policy:

- Keep entries concise and tied to terms already used by lore, calendars,
  languages, sites, or simulation concepts.
- Do not use glossary entries to rename ids, sites, races, jobs, factions, or
  language keys.
- Avoid blank terms and duplicate terms. Terms that collapse to the same
  inspection key, such as `Star-Road` and `Star Road`, are treated as
  duplicates for authoring review.
- The authoring summary exposes `glossary_count` and sorted `glossary_keys`
  for bundle swap checks.

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

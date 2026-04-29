# Language Engine Authoring Notes

`fantasy_simulator.language` is the procedural language package for generated
names, historical sound change, and world-facing endonyms.

## Responsibility Split

- `fantasy_simulator/language/schema.py`
  - Structured sound-change rule DTOs and validation constants.
- `fantasy_simulator/language/phonology.py`
  - Tokenization, feature-class matching, and ordered sound-change application.
- `fantasy_simulator/language/state.py`
  - Runtime-only evolution records and mutable language state.
- `fantasy_simulator/language/presets.py`
  - Historically inspired rule pools keyed by `inspiration_tags`.
- `fantasy_simulator/language/engine.py`
  - The main authoring/debug surface for lexicon generation, naming pools,
    toponym generation, productive-rule selection, and runtime evolution.

`World` owns only the active runtime state and delegates language work through
`world_language.py`. Static bundle data must remain immutable during
simulation; all historical drift lives in `LanguageRuntimeState`.

## Static Vs Runtime

- `LanguageDefinition`
  - Authored once in the `SettingBundle`.
  - Contains the base inventory, author-defined rules, optional feature
    subsets, and `inspiration_tags`.
- `LanguageRuntimeState`
  - Created and mutated by simulation.
  - Stores applied runtime rules plus derived naming/toponym material.
- `LanguageEvolutionRecord`
  - The durable history log used for replay and migration compatibility.

Persistence contract:

- `language_evolution_history` is the canonical durable record.
- `language_runtime_states` is a derived cache stored for convenience.
- When history exists, load rebuilds runtime state from that history so the
  "runtime-state present" and "history replay" restore paths remain
  semantically equivalent.
- If history is absent, persisted runtime state is used as-is.
- If neither exists, the bundle's static language definition is the complete
  source of truth.
- Cross-area serialization precedence is summarized in
  [`serialization_contract.md`](serialization_contract.md).

## Rule Order

Rule application is ordered and deterministic.

Effective surface-form evaluation uses:

1. legacy `sound_shifts`
2. authored `sound_change_rules`
3. runtime-applied rules from `LanguageRuntimeState`

Within a pass, rules are applied in list order. Multiple passes are allowed
until the token stream stabilizes or the pass cap is reached. This means rule
order is part of the authored contract: if two rules can both match, the earlier
rule gets first access to the current token stream.

Evolution rule selection is separate from surface evaluation:

1. inherited `evolution_rule_pool`
2. local `evolution_rule_pool`
3. preset rules from `inspiration_tags`
4. fallback drift if no productive authored/preset rule changes any sampled form

Only productive candidate rules are selected for runtime evolution. A rule that
cannot change any sampled surface form in the current language state is skipped.

## Feature-Based Phonology

Context descriptors such as `front_vowel`, `back_vowel`, `liquid`, and
`fricative` are matched against feature classes, not raw string heuristics at
call sites.

Feature classes are built from:

- the base `vowels` / `consonants` inventory
- explicit feature subsets such as `front_vowels`
- promoted extra segments discovered from:
  - legacy `sound_shifts`
  - active authored/runtime rules
  - authored `evolution_rule_pool` segments when feature classes are prepared

This promotion step matters when a rule target is outside the original base
inventory. Later contextual rules must still recognize the derived segment as a
vowel/consonant/front-vowel/etc., otherwise chained historical changes will
under-apply.

## `inspiration_tags`

`inspiration_tags` opt a language into rule presets from
`fantasy_simulator/language/presets.py`.

These tags are:

- inspiration only, not claims of linguistic accuracy
- additive to the language's own `evolution_rule_pool`
- deterministic once selected into the bundle

Current tags include Romance-, Celtic-, Germanic-, and Turkic-like rule pools.
They should be used to push a language toward a recognizable developmental
flavor, not to mirror a real language one-to-one.

## Endonyms And System Aliases

There are two related but different concepts:

- `location_endonym(location_id)`
  - The current site-native name resolved from static `native_name` or from the
    active language engine.
- `LocationState.aliases`
  - The visible alias list persisted on the location.

Contract:

- Generated endonyms are stored separately on `LocationState.generated_endonym`.
- World-memory aliases remain in `LocationState.aliases`.
- Save/load must be able to regenerate missing generated endonyms from runtime
  state or history replay without consuming alias capacity.
- When a bundle update rebases the language tree, stale generated endonyms from
  the previous language state should be dropped and replaced by the current one.
- User-added aliases should continue to survive normal structural rebuilds.

If debugging alias behavior, compare:

- `world.location_endonym(location_id)`
- `world.get_location_by_id(location_id).generated_endonym`
- `world.get_location_by_id(location_id).aliases`
- `world.language_status()`
- serialized `language_runtime_states`
- serialized `language_evolution_history`

`world.language_status()` is a summary/debug surface, not a lossless snapshot.
It intentionally shows recent evolution records and short sample prefixes. For
full forensic comparison, pair it with serialized runtime state and history.

## Debugging Checklist

Current `resolve_language()` fallback contract:

1. exact selector match
2. partial best match among the selectors that were provided
3. highest-priority `is_lingua_franca`
4. if exactly one language exists, use that
5. otherwise return `None`

Higher-level callers such as `CharacterCreator` may still apply a legacy
`naming_rules` fallback after language resolution fails.

- Surface form changed unexpectedly:
  - Inspect `LanguageEngine.effective_sound_shift_map()`
  - Inspect authored rule order and runtime-applied rules
  - Verify feature subsets and promoted segments
- Evolution did not happen:
  - Check `evolution_interval_years`
  - Check `language_origin_year`
  - Confirm the candidate rule is productive on sampled forms
- Save/load mismatch:
  - Compare a runtime-state save with a history-replay-only save
  - If both are present, treat `language_evolution_history` as the source of truth
  - Confirm generated endonyms regenerate after hydration
  - Confirm `language_evolution_history` and `language_runtime_states` tell the
    same story

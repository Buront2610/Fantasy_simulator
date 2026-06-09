"""Setting-bundle authoring command line helpers.

This module intentionally stays read-only: it validates and previews bundle
data without mutating authored JSON files.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Sequence

from .language_families import language_atlas_lines
from .semantic_roots import build_semantic_root_preview, semantic_root_coverage_lines
from .setting_bundle import build_setting_bundle_authoring_summary, load_setting_bundle


def _load(path: str):
    return load_setting_bundle(Path(path))


def _cmd_validate(args: argparse.Namespace) -> int:
    bundle = _load(args.bundle)
    print(f"valid: {bundle.world_definition.world_key}")
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    summary = build_setting_bundle_authoring_summary(_load(args.bundle))
    if args.json:
        print(json.dumps(asdict(summary), ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    print(f"world: {summary.world_key} ({summary.display_name})")
    print(f"sites: {summary.site_count}")
    print(f"routes: {summary.route_count}")
    print(f"languages: {summary.language_count}")
    print(f"language families: {summary.language_family_count}")
    print(f"semantic roots: {summary.semantic_root_count}")
    print(f"language root realizations: {summary.language_root_realization_count}")
    print(f"cultures: {summary.culture_count}")
    print(f"factions: {summary.faction_count}")
    print(f"faction relationships: {summary.faction_relationship_count}")
    if summary.faction_relationship_status_counts:
        counts = ", ".join(
            f"{status}={count}"
            for status, count in summary.faction_relationship_status_counts.items()
        )
        print(f"faction relationship statuses: {counts}")
    if summary.site_ids_without_language_key:
        print("missing site language keys: " + ", ".join(summary.site_ids_without_language_key))
    if summary.site_ids_without_language_community:
        print("missing language communities: " + ", ".join(summary.site_ids_without_language_community))
    return 0


def _cmd_preview_map(args: argparse.Namespace) -> int:
    world = _load(args.bundle).world_definition
    if not world.site_seeds:
        print("(empty map)")
        return 0
    max_x = max(seed.x for seed in world.site_seeds)
    max_y = max(seed.y for seed in world.site_seeds)
    cells = {(seed.x, seed.y): seed for seed in world.site_seeds}
    for y in range(max_y + 1):
        row = []
        for x in range(max_x + 1):
            seed = cells.get((x, y))
            row.append(seed.region_type[:1].upper() if seed is not None else ".")
        print(" ".join(row))
    if args.legend:
        for seed in sorted(world.site_seeds, key=lambda item: (item.y, item.x, item.location_id)):
            print(f"{seed.x},{seed.y}: {seed.location_id} | {seed.name} | {seed.region_type}")
    return 0


def _language_preview_lines(bundle_path: str, *, limit: int) -> Iterable[str]:
    world = _load(bundle_path).world_definition
    for language in sorted(world.languages, key=lambda item: item.language_key):
        stems = ", ".join(language.name_stems[:limit]) or "-"
        toponyms = ", ".join(language.toponym_stems[:limit]) or "-"
        suffixes = ", ".join(language.toponym_suffixes[:limit]) or "-"
        yield f"{language.language_key}: names [{stems}] | toponyms [{toponyms}] | suffixes [{suffixes}]"


def _cmd_preview_names(args: argparse.Namespace) -> int:
    for line in _language_preview_lines(args.bundle, limit=max(1, args.limit)):
        print(line)
    return 0


def _cmd_preview_roots(args: argparse.Namespace) -> int:
    world = _load(args.bundle).world_definition
    selected_language = args.language or None
    for line in semantic_root_coverage_lines(world, language_key=selected_language):
        print(line)
    if args.roots:
        root_keys = [root.strip() for root in args.roots.split(",") if root.strip()]
        if not root_keys:
            return 0
        language_keys = [args.language] if args.language else [language.language_key for language in world.languages]
        for language_key in language_keys:
            preview = build_semantic_root_preview(world, language_key, root_keys)
            missing = f" | missing: {', '.join(preview.missing_root_keys)}" if preview.missing_root_keys else ""
            components = ", ".join(preview.component_surfaces) or "-"
            print(f"{language_key}: {preview.surface or '-'} [{components}]{missing}")
    return 0


def _cmd_preview_language_atlas(args: argparse.Namespace) -> int:
    world = _load(args.bundle).world_definition
    for line in language_atlas_lines(world):
        print(line)
    return 0


def _cmd_diff(args: argparse.Namespace) -> int:
    old = build_setting_bundle_authoring_summary(_load(args.old_bundle))
    new = build_setting_bundle_authoring_summary(_load(args.new_bundle))
    old_summary = asdict(old)
    new_summary = asdict(new)
    changed = False
    for field in sorted(old_summary):
        old_value = old_summary[field]
        new_value = new_summary[field]
        if old_value != new_value:
            changed = True
            if isinstance(old_value, (int, str)) and isinstance(new_value, (int, str)):
                print(f"{field}: {old_value} -> {new_value}")
            else:
                print(f"{field} changed")
    if not changed:
        print("authoring summary diff: no authoring summary field changes")
    else:
        print("authoring summary diff: changes shown above")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m fantasy_simulator.content")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("bundle")
    validate.set_defaults(func=_cmd_validate)

    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("bundle")
    inspect.add_argument("--json", action="store_true")
    inspect.set_defaults(func=_cmd_inspect)

    preview_map = subparsers.add_parser("preview-map")
    preview_map.add_argument("bundle")
    preview_map.add_argument("--legend", action="store_true")
    preview_map.set_defaults(func=_cmd_preview_map)

    preview_names = subparsers.add_parser("preview-names")
    preview_names.add_argument("bundle")
    preview_names.add_argument("--limit", type=int, default=3)
    preview_names.set_defaults(func=_cmd_preview_names)

    preview_roots = subparsers.add_parser("preview-roots")
    preview_roots.add_argument("bundle")
    preview_roots.add_argument("--language", default="")
    preview_roots.add_argument("--roots", default="")
    preview_roots.set_defaults(func=_cmd_preview_roots)

    preview_language_atlas = subparsers.add_parser("preview-language-atlas")
    preview_language_atlas.add_argument("bundle")
    preview_language_atlas.set_defaults(func=_cmd_preview_language_atlas)

    diff = subparsers.add_parser("diff")
    diff.add_argument("old_bundle")
    diff.add_argument("new_bundle")
    diff.set_defaults(func=_cmd_diff)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Setting bundle authoring CLI smoke tests."""

from __future__ import annotations

import json

from fantasy_simulator.content.__main__ import main
from fantasy_simulator.content.setting_bundle_source import DEFAULT_AETHORIA_BUNDLE_PATH


def test_content_validate_accepts_bundled_aethoria(capsys) -> None:
    exit_code = main(["validate", str(DEFAULT_AETHORIA_BUNDLE_PATH)])

    assert exit_code == 0
    assert "valid:" in capsys.readouterr().out


def test_content_inspect_json_reports_authoring_summary(capsys) -> None:
    exit_code = main(["inspect", str(DEFAULT_AETHORIA_BUNDLE_PATH), "--json"])

    assert exit_code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["site_count"] > 0
    assert data["language_count"] > 0
    assert "language_keys" in data


def test_content_preview_map_and_names_are_nonempty(capsys) -> None:
    assert main(["preview-map", str(DEFAULT_AETHORIA_BUNDLE_PATH)]) == 0
    map_output = capsys.readouterr().out
    assert "." in map_output or "C" in map_output

    assert main(["preview-names", str(DEFAULT_AETHORIA_BUNDLE_PATH), "--limit", "2"]) == 0
    names_output = capsys.readouterr().out
    assert "names [" in names_output

    assert main([
        "preview-roots",
        str(DEFAULT_AETHORIA_BUNDLE_PATH),
        "--language",
        "aethic_common",
        "--roots",
        "dark,pass",
    ]) == 0
    roots_output = capsys.readouterr().out
    assert "semantic roots:" in roots_output
    assert "aethic_common:" in roots_output
    assert "Blackgap [black, gap]" in roots_output

    assert main(["preview-language-atlas", str(DEFAULT_AETHORIA_BUNDLE_PATH)]) == 0
    atlas_output = capsys.readouterr().out
    assert "language families:" in atlas_output
    assert "aethic_family:" in atlas_output
    assert "aethic_common" in atlas_output


def test_content_preview_map_legend_lists_site_details(capsys) -> None:
    exit_code = main(["preview-map", str(DEFAULT_AETHORIA_BUNDLE_PATH), "--legend"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "loc_aethoria_capital" in output
    assert "Aethoria Capital" in output


def test_content_validate_reports_invalid_path(capsys) -> None:
    exit_code = main(["validate", "missing-bundle.json"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "error:" in captured.err
    assert "missing-bundle.json" in captured.err


def test_content_diff_reports_no_changes_for_same_bundle(capsys) -> None:
    exit_code = main([
        "diff",
        str(DEFAULT_AETHORIA_BUNDLE_PATH),
        str(DEFAULT_AETHORIA_BUNDLE_PATH),
    ])

    assert exit_code == 0
    assert "authoring summary diff: no authoring summary field changes" in capsys.readouterr().out


def test_content_diff_reports_changed_route_count(tmp_path, capsys) -> None:
    changed_bundle = tmp_path / "aethoria-without-one-route.json"
    data = json.loads(DEFAULT_AETHORIA_BUNDLE_PATH.read_text(encoding="utf-8"))
    route_seeds = data["world_definition"]["route_seeds"]
    original_route_count = len(route_seeds)
    route_seeds.pop()
    changed_bundle.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    exit_code = main([
        "diff",
        str(DEFAULT_AETHORIA_BUNDLE_PATH),
        str(changed_bundle),
    ])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "authoring summary diff" in output
    assert f"route_count: {original_route_count} -> {original_route_count - 1}" in output

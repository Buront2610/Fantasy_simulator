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


def test_content_diff_reports_no_changes_for_same_bundle(capsys) -> None:
    exit_code = main([
        "diff",
        str(DEFAULT_AETHORIA_BUNDLE_PATH),
        str(DEFAULT_AETHORIA_BUNDLE_PATH),
    ])

    assert exit_code == 0
    assert "no authoring summary changes" in capsys.readouterr().out

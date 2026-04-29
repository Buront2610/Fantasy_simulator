"""Language selection screen helper."""

from __future__ import annotations

from ..i18n import set_locale, tr
from .ui_context import UIContext, _default_ctx


def _select_language(ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    action = ctx.choose_key(
        tr("load_language_prompt"),
        [
            ("ja", tr("language_option_ja")),
            ("en", tr("language_option_en")),
        ],
        default="1",
    )
    if action == "ja":
        set_locale("ja")
        ctx.out.print_success(f"  {tr('language_set_ja')}")
    else:
        set_locale("en")
        ctx.out.print_success(f"  {tr('language_set_en')}")

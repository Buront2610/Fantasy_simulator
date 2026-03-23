# PR #28 Review — "PR-D: Wire InputBackend/RenderBackend through screens.py, main.py, character_creator.py"

前回のレビューで挙げた4大課題（backend が死にコード・直 print/input・CharacterCreator 未抽象化・統合テスト不足）は今回の PR で解消されており、大幅な改善と評価できます。
以下は現コードに残る課題のみを記します。

---

## 1. スタイル責務の漏れ（前回指摘の継続・重点）

`screens.py` と `main.py` は `bold()`, `green()`, `yellow()`, `red()`, `dim()`, `cyan()` を直接インポートし、ANSI 付き文字列を自前で組み立ててから `out.print_line()` に渡しています。

```python
# screens.py (例)
out.print_line(f"  {bold(tr('running_simulation_details', years=years, events=8))}")
out.print_line(f"  {tr('year_label')} {world.year}  |  {green(str(alive))} {tr('alive')}")
out.print_line(f"  {yellow('!')}  {tr('auto_paused_after', years=years)}: {reason_text}")
out.print_line(f"  {cyan(rname)}")  # screen_world_lore

# main.py
out.print_line(yellow(HEADER))
out.print_line(f"\n  {bold(yellow(tr('farewell')))}\n")
```

`RenderBackend` には `print_success`, `print_warning`, `print_error`, `print_heading`, `print_dim` という**意味的な API** がすでに存在しますが、その横で多くの箇所が ANSI ヘルパーをそのまま使い続けています。
将来 Rich/Textual に差し替えたとき、ANSI 文字列を埋め込んだ `print_line()` 呼び出しはすべて壊れます。

**提案**:

| 現状 | 置き換え案 |
|---|---|
| `out.print_line(f"  {green('*')}  {msg}")` | `out.print_success(f"  {msg}")` |
| `out.print_line(f"  {yellow('!')}  {msg}")` | `out.print_warning(f"  {msg}")` |
| `out.print_line(f"  {bold(label)}")` | `out.print_heading(label)` |
| `out.print_line(f"  {cyan(name)}")` | `out.print_highlighted(name)` (要追加) |

少なくとも「生死を色で表す」「! や * の意味マーカー」の部分は semantic API に寄せると、backend 切り替えが現実的になります。

---

## 2. InputBackend の契約と実装のズレ（前回指摘の継続・重点）

### 2a. `choose_key()` の `prompt` 引数が無視される

`InputBackend.Protocol` は `prompt` を受け取る契約ですが、`StdInputBackend.choose_key()` は `_choose_key()` に委譲し、その内部は `prompt` を一切使わず `tr('your_choice')` で固定されたプロンプトを表示します。

```python
# StdInputBackend
def choose_key(self, prompt, key_label_pairs, default=None):
    from .ui_helpers import _choose_key
    return _choose_key(prompt, key_label_pairs, default)  # prompt は _choose_key 内で無視される

# _choose_key 内
raw = input(f"  {bold(tr('your_choice'))}{hint}: ").strip()  # prompt 引数を使わない
```

呼び出し側 (`_show_results`, `main()` など) は `tr("what_to_view")`, `tr("main_menu_prompt")` 等を渡しているので、これらが表示されると期待するかもしれませんが、実際には無視されます。

**修正案**: `_choose_key()` が `prompt` 引数をメニュー見出しとして表示する（またはヘッダー行として `out.print_line(prompt)` する）か、呼び出し側は `prompt` をメニュー外で別途 `out.print_line()` で表示する設計に統一する。

### 2b. `pause()` の `message` 引数が無視される

```python
# StdInputBackend
def pause(self, message: str = "") -> None:
    from .ui_helpers import _pause
    _pause()  # message は渡さない

# _pause
def _pause() -> None:
    input(dim(f"\n  {tr('press_enter')} "))  # 固定文言
```

Protocol 上は `pause(message="Save completed!")` のように呼べる設計ですが、`StdInputBackend` はそれを無視します。今は呼び出し側も全て `pause()` or `inp.pause()` と引数なしで呼んでいるので実害はありませんが、API 契約として不誠実です。

**修正案**: `_pause(message: str = "")` がメッセージを表示できるよう拡張し、`StdInputBackend.pause()` が `_pause(message)` に渡す。

---

## 3. `print_wrapped` の間接委譲

`PrintRenderBackend.print_wrapped()` は `_print_wrapped()` に委譲しており、その内部は `print()` を直接使います。

```python
# PrintRenderBackend
def print_wrapped(self, text: str, indent: int = 4) -> None:
    from .ui_helpers import _print_wrapped
    _print_wrapped(text, indent)  # _print_wrapped 内が直接 print()

# _print_wrapped
def _print_wrapped(text, indent=4):
    ...
    print(wrapped)  # 直接 print()
```

標準 backend の内部実装として機能はしますが、他の `PrintRenderBackend` メソッドは全て `print()` を直接呼んでいる一方、`print_wrapped` だけ helper に委譲するという非対称があります。
設計の一貫性のため、`PrintRenderBackend.print_wrapped()` 自身が wrap を生成して `self.print_line(line)` で出力するか、あるいは `_print_wrapped()` を backend 内部に完全に取り込む形が望ましいです。

---

## 4. stdout 漏れテストのカバレッジ不足

`TestNoPrintLeaks` は `_show_roster`, `_select_language`, `screen_world_lore` の3ケースのみを `redirect_stdout` でチェックしています。
しかし最も複雑な I/O パス（`screen_new_simulation`, `_run_simulation`, `_advance_simulation`, `screen_custom_simulation`）は**カバーされていません**。

`test_new_sim_output_through_backend` は `len(out.calls) > 5` だけを確認しており、stdout への漏れは検証していません。

**提案**: `screen_new_simulation` 相当のパスにも `redirect_stdout` テストを追加する：

```python
def test_run_simulation_produces_no_stdout(self) -> None:
    from fantasy_simulator.ui.screens import screen_new_simulation
    out = RecordingRenderBackend()
    inp = ScriptedInputBackend(answers=["4", "1"], menu_keys=["back_to_main"])
    ctx = UIContext(inp=inp, out=out)
    captured = io.StringIO()
    with redirect_stdout(captured):
        screen_new_simulation(ctx=ctx)
    self.assertEqual(captured.getvalue(), "")
```

---

## 5. 軽微な観察点

### 5a. `StdInputBackend.choose_key()` が `_choose_key()` 内で `print()` を呼ぶ
`ScriptedInputBackend` を使ったテストは `print()` を呼ばないため stdout はクリーンですが、`StdInputBackend` を使うと `_choose_key()` 内の `print()` が stdout に出ます。これは設計通りですが、「`out` backend を通じてメニューを描画したい」という将来的な要求とは相性が悪いです。現時点では許容範囲。

### 5b. `simulation_summary` / `character_story` の表示生成は domain 側
`sim.get_summary()`, `sim.get_character_story()`, `sim.get_all_stories()` は ANSI を含まない純粋なテキストを返すので現状は許容できますが、表示フォーマットの生成が domain 層（`simulation/queries.py`）に入り込んでいます。今後 view の分離を進める場合はここがボトルネックになります（今回のスコープ外として構いません）。

---

## 総評

WIP としてはかなり良い状態です。backend の配線は機能しており、テスト構造も整っています。
マージを検討するなら **課題 2（InputBackend 契約のズレ）** が最優先で、`prompt`/`message` が無視されるのは API 嘘になるので直すべきです。
**課題 1（スタイル責務）** は今のままでも動きますが、`RenderBackend` を本当に抽象として活用したいなら段階的に semantic API に寄せることを推奨します。
**課題 4（stdout テストのカバレッジ）** も比較的低コストで追加できるので、CI の信頼性向上のために追加を推奨します。

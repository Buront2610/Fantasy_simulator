# 統合負債台帳（2026-06-10）

設計負債・技術的負債を全ソースから集約した単一インデックス。
個々の詳細は各ソースを正とし、本書は横断ビューと返済優先順位を提供する。

**ソース台帳**（既存の可視化資産）:

| ソース | 内容 | 状態 |
|---|---|---|
| `architecture_guard.json` complexity.overrides | 複雑度バジェット超過 32 件（`removal_condition` 付き） | 稼働中 |
| `docs/td_backlog_status.md` | TD-1〜TD-4 の完了監査ログ | **全件クローズ済み** |
| `docs/risk_register.md` | 残存リスク 8 件＋完了ガードレール | 稼働中 |
| `docs/technical_review_action_plan.md` | 前回技術レビュー（2026-05-29、8/10）由来の TR-0〜15 | 一部完了 |
| `docs/review_report_2026-06-10.md` | 本レビュー: バグ・バランス・ロードマップ | 新規 |
| `docs/design_philosophy_review_2026-06-10.md` | 本レビュー: 再設計対象 R1〜R9・規約 | 新規 |

**特筆**: コード内の TODO / FIXME / HACK コメントは **0 件**（grep 確認済み）。
負債はすべて台帳で管理されており、コードに散逸していない。この管理文化は優秀。

---

## 1. 全体サマリ

| カテゴリ | 件数 | 深刻度 | 管理場所 |
|---|---|---|---|
| A. 欠陥負債（未修正バグ） | 6 | **高 2 / 中 4** | review_report §3 |
| B. 設計負債（再設計対象） | 9（うち 2 は規約化で解消） | 高 1 / 中 4 / 低 2 | design_philosophy_review §3 |
| C. 複雑度負債（guard overrides） | 32 | 低（台帳管理済み） | architecture_guard.json |
| D. 互換層負債（意図的維持） | 4 系統 | 低（縮退済み） | td_backlog_status / risk_register |
| E. 残存リスク | 8 | 中 | risk_register |
| F. 技術レビュー行動計画の残項目 | 約 6 | 中 | technical_review_action_plan |
| G. ドキュメント/プロセス負債 | 4 | 中 | review_report §7 |
| H. ゲームデザイン負債（体験負債） | 7 | **高**（製品価値に直結） | review_report §2–§5 |
| I. UX / i18n 負債 | 10 | 中 2 / 低 8 | review_report §7（本書 §11 で台帳化） |
| J. 成長・性能・開発速度負債 | 4 | 中 | 本書 §12（2026-06-10 実測） |
| K. 型安全の部分性 | 1 | 低〜中 | technical_review 由来（本書 §13） |

---

## 2. カテゴリ A: 欠陥負債（未修正バグ — 最優先返済）

実行再現済み。詳細・修正方法は `review_report §3`。

| # | 重要度 | 内容 |
|---|---|---|
| 1 | High | パーティ冒険中のメンバー死亡で生存者の `active_adventure_id` 永久残留 |
| 2 | Med-High | 同経路で慰霊碑が存命リーダー名義になる（#1 と同一修正） |
| 3 | Medium | 季節補正デルタ非シリアライズ → 月中セーブで恒久焼き付き |
| 4 | High | セーブ非アトミック → 書込失敗で既存セーブ破壊 |
| 5 | Medium | スコア 0 関係性がロードで消失 |
| 6 | Medium | `migrate_v1_to_v2` 非冪等 / v5→v6・v6→v7 の無条件再構築 |

## 3. カテゴリ B: 設計負債（再設計対象 R1〜R9）

詳細は `design_philosophy_review §3`。

- **解消済み（規約化）**: R1（プロセス状態シリアライズ → 規約 10）、R3（DbC 二流派 → 規約 9）。
  ただし規約は書いただけであり、**既存コードの規約適合監査は未実施**（季節デルタは違反例として残存 = バグ #3）
- **未着手・高**: R2（ルートドメイン→ui 依存の封鎖。`world.py:265`、`character_creator/interactive.py`）
- **未着手・中**: R4（world コンテキストの物理化、ルート 103 モジュール）、
  R5（ミックスイン暗黙 self 共有 → AppService 時に解消）、R6（AppService の JSON 型規律）
- **未着手・低**: R7（World ゴッド・アグリゲート）、R8（`max_module_lines` バジェット不在と
  gate 過剰化リスク、view_models.py 1,162 行）、R9（mypy 対象の二重管理）

## 4. カテゴリ C: 複雑度負債（guard overrides 32 件）

全件 `removal_condition` 付きで台帳管理済み。内訳の偏りが返済戦略を示す。
ただし SRP / complexity guard は過剰に細分化を促す可能性もあるため、override 削減そのものを
目的化しない。返済時は「分割で凝集・変更容易性・レビュー容易性が上がるか」と「ゲート閾値が
プロジェクト固有の実害を検出しているか」を同時に確認する:

| 系統 | 件数 | 傾向 |
|---|---|---|
| World 系ファサード/ミックスイン（world.py、world_*_api） | 7 | **R4（コンテキスト物理化）と同根**。物理化の際に一括返済可能 |
| UI 地図/アトラス描画（atlas_*、map_*、screen_results） | 8 | 描画アルゴリズムの本質的複雑さ。優先度低 |
| 言語エンジン（phonology、evolution、naming） | 3 | データテーブル化候補と自己申告済み |
| レガシー互換（Character、WorldEventRecord、reports、migration、timeline 等） | 9 | 互換層の縮退と連動 |
| その他（terrain クラスタリング、伝播、render backend protocol） | 5 | 個別判断 |

**観察**: override の 1/4 が world 系。R4 を実施すれば複雑度負債も同時に大きく減る。

## 5. カテゴリ D: 互換層負債（意図的に維持されているもの）

TD-1〜TD-3 で「縮退済み・runtime projection 化済み」と監査されており、**返済不要・監視のみ**:

- `simulator.py`（11 行の純粋再エクスポート）
- `Simulator.history` / `event_log`（canonical `event_records` からの互換投影）
- `world_data.py` の lore/race/job legacy projection（bundle-first 移行済み、制約テスト管理）
- `World.render_map()` の ui 遅延 import（ただしこれは R2 の対象として deprecation 予定）

## 6. カテゴリ E: 残存リスク（risk_register より要約）

1. PR-K 完了状態のドキュメント乖離（agents が古いマイルストーンで作業するリスク）
2. canonical records と legacy adapters の乖離
3. PR-K コマンド境界 ID の非正規化回帰
4. **通常イベントの semantic rendering coverage が部分的**（新イベント族が summary_key を省略するリスク。docx P0-1 と同件）
5. 言語 runtime cache と durable history の乖離
6. ドキュメントが契約変更に遅れる
7. hydration precedence の無テスト変更
8. era runtime 永続化の意図的延期（ADR-0003。早期永続化はスキーマ衝突を生む）

## 7. カテゴリ F: 技術レビュー行動計画（TR-0〜15）の残項目

完了済み: TR-3（roadmap sync）、TR-9（performance regression guard）、
TR-4〜TR-8 相当（event index write path / serializer・hydrator 分割 — risk_register と
現行コード `world_persistence/serializer.py` / `world_persistence/hydrator.py` で完了を確認）。

**残**: TR-1（Python 3.10 出口 ADR）、TR-10/11（semantic rendering 移行の残り —
リスク E-4 と同件）、TR-12（auto-pause 走査集約）、TR-13（自前 guard と外部ツール棚卸し）、
TR-14（RouteEdge identity mutation 閉鎖）、TR-15（headless view model contract —
**docx UI-0 AppService / R6 と同件に統合すべき**）。

## 8. カテゴリ G: ドキュメント/プロセス負債

1. CLAUDE.md のアーキテクチャ図がルート 103 モジュールの現実と乖離（R4 と同時に更新）
2. ブランチ `codex/architecture-fitness-guard` の責務混在（ガード整備＋大型機能 52 コミット
   +12.6k 行。ガード部分の先行 PR 切り出し推奨）
3. mypy 対象リストの CI / quality_gate 二重管理（R9）
4. **台帳の分散という新たなメタ負債**: 負債が 6 ソースに分散し、横断ビューがなかった
   （本書がその対処。今後は本書を負債のトップレベル・インデックスとして維持し、
   各台帳更新時に本書のサマリ表を追随させる）

## 9. カテゴリ H: ゲームデザイン負債（体験負債）

構造負債と異なり**製品価値（歴史生成の面白さ）を直接毀損**している。テストプレイ実測で確認済み。
World Health Check（review_report §15）導入後は xfail(strict=True) 台帳として管理する。

| # | 内容 | 対応計画 |
|---|---|---|
| H1 | 人口補充メカニクス不在（世界が必然的に絶滅） | ロードマップ 1（流入） |
| H2 | 結婚が実質成立不能（200 年で 0 件） | ロードマップ 7 |
| H3 | スキル・魔法が判定に未接続（完全フレーバー） | ロードマップ 3（TRPG 戦闘） |
| H4 | 冒険リスク飽和（danger もポリシーも結果に反映されず、death 0%） | ロードマップ 1 |
| H5 | 世界変化が因果なきサイコロ（era 16 回/100 年、空っぽの戦争） | ロードマップ 2（WorldArc） |
| H6 | 加齢帯の絶対年齢固定（長寿種族が同一プロファイルへ収束） | ロードマップ 7 |
| H7 | 戦闘ログが結果から逆算された演出（実判定と無関係） | ロードマップ 3 |

## 11. カテゴリ I: UX / i18n 負債（review_report §7 から台帳化漏れしていたもの）

| # | 重要度 | 内容 |
|---|---|---|
| I1 | 中 | EOFError 全体未処理（パイプ枯渇・Ctrl+Z+Enter で生トレースバッククラッシュ） |
| I2 | 中 | セーブ上書き確認なし（`screen_persistence.py:18-21`）＋未セーブ離脱警告なし（`screen_results.py:112-113`） |
| I3 | 低 | TERMS_EN に地域タイプ未登録（英語 UI で生キー表示） |
| I4 | 低 | `ui_helpers.py:147` の "default" 直書き（Rich 側は tr() 使用で不統一） |
| I5 | 低 | JA テキスト内 `Year {year}:` 英語混入 約 25 キー |
| I6 | 低 | ロア本文・種族説明がバンドル由来の英語のみ（JA ロケールで言語混在） |
| I7 | 低 | 結果メニューが 20 項目フラット（グループ化余地） |
| I8 | 低 | イベントログ全件表示にページングなし |
| I9 | 低 | レガシーグリッドが 108 桁で 80 桁端末で崩れる |
| I10 | 低 | アトラスラベル配置が文字数ベース（全角地名で桁ズレの潜在バグ） |

## 12. カテゴリ J: 成長・性能・開発速度負債（2026-06-10 実測）

| # | 重要度 | 内容 | 実測値 |
|---|---|---|---|
| J1 | 低〜中 | **テストスイート実行時間の変動が大きい**: 初回計測 417 秒（1,800 件）に対し、quality_gate 経由の再計測では 78 秒（1,807 件）。コールド FS キャッシュ / Defender スキャン等の環境要因で 5 倍以上振れる。ウォーム時 約 80 秒なら階層化の緊急度は低いが、変動要因の特定（pytest-cov 設定有無等）と、AI エージェント向けに「速い検証コマンド」（focused suite 約 50–70 秒）の案内を CLAUDE.md に明記する価値はある | 417.6s（初回）/ 77.6s（ウォーム） |
| J2 | 中 | **event_records / rumor_archive に上限・圧縮ポリシーなし**。現状「増殖が穏やか」に見えるのは人口絶滅（H1）が成長をマスクしているため。20 人維持で 1000 年なら save 約 35MB 規模に線形成長する見込み。H1 修正と同時に顕在化する | 150 年（世界死亡時点）で records 2,332・save 4.1MB |
| J3 | 低→中 | **ローカル開発環境で quality_gate が実行不能だった**。(a) dev 依存未インストール（flake8/mypy/hypothesis 不在、property テストはサイレントスキップ）、(b) flake8 exclude に `.trunk`（Trunk リンターのローカルキャッシュ、意図的に不正なテストデータを含む）が漏れており、依存導入後も `.trunk` 由来の偽陽性で gate が失敗。2026-06-10 に両方解消済み（`pip install -e ".[dev]"` 実施、`.trunk` を quality_gate.py / CLAUDE.md / AGENTS.md の exclude に追加）。再発防止には gate 冒頭での依存検証の自動化が望ましい | gate 失敗 2 回を実測 |
| J4 | 低 | 開発機は Python 3.13 だが CI マトリクスは 3.10–3.12。テスト環境と実行環境の乖離 | — |
| J5 | **中〜高** | **キャラ数に対する超線形スケーリング（実測指数 ≈1.7、ほぼ二乗）**。20 キャラ 0.10 秒/年 → 100 キャラ 1.63 秒/年（16 倍）。原因はペア全走査系（関係・イベント候補選定）と推定。**人口増加（H1）を入れると顕在化する**——100 キャラ × 1000 年は約 27 分。H1 と同時にプロファイリング＋候補選定の局所化（同一拠点限定等）が必要 | 100 chars × 30y = 49.0s、peak メモリ 8MB（メモリは健全） |

シミュレーション速度は**小人口では**健全: 約 0.1 秒/年（20 キャラ）で年数に線形、300 年 30.6 秒。
カバレッジ実績: 87.8%（最低 narrative 72% / ui 79%。ただし計測が約 2.5 ヶ月前と古い — 定期再計測を CI に）。

**J1 の返済案**: 高速/低速のテスト階層化（`@pytest.mark.slow` ＋ デフォルト除外）、pytest-xdist 並列化、
quality_gate プロファイルへの組み込み。World Health Check の 2 層構成（§15）と同じ思想で統一する。
**J2 の返済案**: H1 着手時に併せて、アーカイブの世代別圧縮（古い低 severity レコードの要約化）または
上限＋ローテーションのポリシーを ADR 化する。

## 13. カテゴリ K: 型安全の部分性

mypy は focused targets（約 70 モジュール）のみで全体カバレッジではない（前回技術レビューの
「部分的型安全」指摘）。ミックスインの暗黙 self 共有（R5）と相互に増幅し合う関係。
全体 mypy 化は大工事のため、**新規パッケージ（world_change / observation / language / 今後の app/）を
必ず対象に含める追加ルール**で漸進するのが現実的。

## 14. 監査済み・負債なしと確認した領域

- **セキュリティ**: eval/exec 不使用（rng 状態復元は `ast.literal_eval`＋型検証）、保存は JSON のみ、
  CodeQL 稼働。ローカル CLI でネットワーク面なし
- **ランタイム依存**: 標準ライブラリのみ＋optional UI extras。依存腐敗リスクほぼゼロ
- **エンコーディング**: 読み書きとも utf-8 明示で Windows cp932 問題なし
- **リポジトリ衛生**: コード内 TODO ゼロ。軽微: `.coverage` / `.sonar/` / `coverage.xml` /
  `_playtest_*.py` / 本レビューのレポート群が未追跡（.gitignore 整備またはコミットで解消）

## 15. メタ評価と返済優先順位

**健全性**: 負債管理文化は同規模プロジェクトとして例外的に良い。コード内 TODO ゼロ・
全負債が removal_condition / 完了条件付きで台帳化・監査ログまである。
弱点は (a) 台帳が分散し横断ビューがなかったこと（本書で対処）、
(b) **体験負債（カテゴリ H）が負債として認識されていなかったこと** — 構造の負債管理は
完璧だったが、面白さの負債は台帳の外にあった。World Health Check が H を台帳に入れる仕組みになる。

**返済優先順位**（review_report §14 ロードマップと整合）:

1. **A（バグ）** — 0a。特に #1/#4 は人口増加・実プレイ前の必須返済
2. **H を計測下に置く** — 0b（World Health Check + xfail 台帳化）。返済そのものはロードマップ 1〜7 で
3. **J5（超線形スケーリングのプロファイリング）** — H1（人口流入）と同一 PR で。J1（スイート実行時間）はウォーム時 80 秒と判明したため優先度を下げ、変動要因の確認のみ
4. **R2 + E-4/TR-10**（ルート→ui 封鎖、semantic coverage）— WorldArc / AppService 着手前の地ならし
5. **J2（レコード成長ポリシー ADR）** — H1（人口流入）の実装と同一 PR で
6. **I1/I2（EOFError・セーブ保護）** — 実プレイ（テストプレイ文化）が始まる前に
7. **R4 + C の world 系 7 件**（コンテキスト物理化と複雑度返済の同時実施）
8. **R6 + TR-15 の統合**（AppService の JSON 契約として一本化）
9. 残り（TR-1/12/13/14、R7/R8/R9、I3〜I10、J3/J4、K、G）は機会返済

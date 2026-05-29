# 技術レビュー対応計画

**作成日**: 2026-05-29  
**対象レビュー**: 技術選定評価 8/10、および主要負債指摘  
**位置づけ**: 本書はレビュー指摘を実装可能な順序へ落とす行動計画である。公式な実装順や PR 分割を変更する場合は、
`docs/implementation_plan.md` を先に更新し、本書はレビュー由来の根拠・受け入れ条件・負債台帳として追随させる。

---

## 1. 方針

レビューの結論は「技術選定は妥当。ただし互換層、永続化、巨大 aggregate、自前ガード、部分的型安全の負債が
将来の変更コストを押し上げる」である。したがって本計画では、新技術の追加ではなく、現在の選定を活かした
負債削減を優先する。

### 1.1 維持する判断

- Python CLI と標準ライブラリ中心の runtime を維持する。
- Rich / prompt_toolkit / wcwidth は optional UI extras のままにする。
- JSON save と schema migration を継続し、DB 導入は行わない。
- Textual 本格導入、Web 化、LLM 常用化は当面の非目標とする。
- `World.event_records` を canonical event store とし、legacy projection は互換層に閉じ込める。

### 1.2 改善対象

1. Python 3.10 minimum の出口計画
2. `architecture_guard.json` overrides の負債台帳化
3. `world_persistence.py` の domain 別 serializer / hydrator 分割
4. 通常イベントの semantic rendering coverage 拡大
5. 自前 guard と外部ツールの役割棚卸し
6. UI framework 導入前の headless view model contract 固定

---

## 2. 優先順位

| 優先 | テーマ | 目的 | 期待効果 |
|---:|---|---|---|
| P0 | 現状固定 | レビュー指摘を台帳化し、進捗を追跡可能にする | 負債の固定資産化を防ぐ |
| P1 | Python version | Python 3.10 EOL 前に最低要件更新の判断点を置く | CI / 配布 / 型機能の先行リスクを下げる |
| P1 | Guard override | 複雑度 override に owner と削除条件を持たせる | 例外予算を削減可能な backlog に変える |
| P1 | Persistence split | hydrate / serialize の横断責務を分割する | save/load regression の事故率を下げる |
| P2 | Semantic events | locale-aware rendering を通常イベントへ広げる | i18n と replay 表示の安定性を上げる |
| P2 | Guard tooling | 自前 guard をゲーム固有ルールへ絞る | guard tool 保守コストを抑える |
| P3 | UI contracts | TUI framework 前に dashboard/report/map contract を固定する | 見た目先行の UI 絡まりを避ける |

---

## 3. 実行計画

### Phase 0: レビュー指摘の台帳化

**目的**: コード挙動を変えずに、レビュー指摘を追跡可能な project artifact にする。

**作業**:

- 本書を追加し、レビュー指摘を優先順位・完了条件・PR 候補へ分解する。
- `docs/implementation_plan.md` との関係を明記し、source of truth の競合を避ける。
- 既存の `docs/risk_register.md` と `docs/td_backlog_status.md` を参照し、
  「閉じた TD batch」と「残っている override debt」を混同しないようにする。
- `docs/td_backlog_status.md` は TD-1〜TD-4 の cleanup batch が閉じたことを示す監査ログとして扱う。
- `docs/risk_register.md` は現行設計に残るリスクと guardrail の確認先として扱い、override debt の削減対象と
  混同しない。

**完了条件**:

- レビュー指摘に対し、最低 1 つ以上の具体的な PR 候補が紐づいている。
- 非目標が明記され、DB / Web / Textual / LLM 常用化へ飛ばない判断が共有されている。

### Phase 1-A: Python 3.10 minimum の出口計画

**目的**: Python 3.10 の EOL 前に、最低 Python version 更新を判断できる状態にする。

**作業**:

- `pyproject.toml`、CI matrix、README、installation docs の Python version 表記を棚卸しする。
- 3.11 minimum と 3.12 minimum の差分を比較する。
- 3.10 を切る場合のユーザー影響、dev dependency、typing 改善余地を短い ADR にまとめる。
- 実際の `requires-python` 変更は、少なくとも 1 PR 前に告知用 doc 更新を入れる。

**完了条件**:

- `docs/adr/` または同等の計画文書に、3.11 / 3.12 / 3.10 継続の判断基準がある。
- CI matrix 変更の候補が明記されている。
- Python minimum 更新 PR の前提条件と rollback 条件が明記されている。

### Phase 1-B: Architecture override debt ledger

**目的**: `architecture_guard.json` の complexity overrides を、単なる例外ではなく削減可能な負債台帳へ変える。

**作業**:

- override ごとに category を付ける。
  - compatibility aggregate
  - persistence / migration
  - semantic rendering gap
  - UI renderer complexity
  - geometry / atlas algorithm
  - intentional protocol surface
- 各 override に削除条件、分割候補、先行テストを持たせる。
- すぐ削れない override は `accepted_until` 相当の見直し時期を文書化する。
- intentional な protocol surface は「残す例外」として別扱いにし、削減対象と混ぜない。

**PR 候補**:

1. `architecture_guard.json` に metadata を足すか、別 doc に override ledger を追加する。
2. guard script が metadata 欠落を検出する lightweight check を追加する。
3. 上位 3 件の override を削減し、ledger の運用を実証する。

**完了条件**:

- 全 override に reason だけでなく、削除または維持の判断軸がある。
- 新規 override 追加時に、削除条件または accepted reason を要求できる。
- 直近 1 つ以上の override が削減され、運用が机上計画で終わっていない。

### Phase 1-C: Persistence serializer / hydrator split

**目的**: `world_persistence.py` の横断的 hydrate / serialize を domain ごとに分割し、保存互換を維持したまま
変更リスクを下げる。

**分割順序**:

1. **Inventory PR**: 現在の save payload section と owner を文書化する。
2. **Read-only helpers PR**: event records / rumors / adventures / memorials / language / terrain の抽出関数を追加する。
3. **Serializer split PR**: payload shape を変えず、domain 別 `serialize_*` へ移す。
4. **Hydrator split PR**: payload precedence を保ったまま、domain 別 `hydrate_*` へ移す。
5. **Contract PR**: conflict precedence tests と old save fixtures を増やす。

**ガードレール**:

- `CURRENT_VERSION` を上げない refactor では、保存 JSON の shape を変えない。
- 旧 schema の backward-load fixture を必ず維持する。
- `docs/serialization_contract.md` の precedence と矛盾する変更をしない。
- terrain snapshot の省略可否、bundle-backed structure、language history precedence は個別テストで固定する。

**完了条件**:

- `hydrate_world_state` と `serialize_world_state` の complexity override が削減または削除される。
- Domain 別 serializer / hydrator は単体テスト可能で、save/load E2E は従来通り通る。
- 保存互換性の変更がある場合は schema migration と serialization contract が同じ PR で更新される。

### Phase 2-A: 通常イベントの semantic rendering coverage 拡大

**目的**: world-change events だけでなく、battle / meeting / journey / relationship / lifecycle などの通常イベントも
`summary_key` + `render_params` を正規化し、locale-aware replay を安定させる。

**作業順**:

1. Event family ごとの現状 inventory を作る。
2. Stored compatibility description に依存している family を優先順位付けする。
3. 1 family ずつ semantic params を追加し、legacy description は projection へ縮退させる。
4. JA / EN rendering snapshot を追加する。
5. `WorldEventRecord` の validation と legacy adapter projection を段階的に薄くする。

**完了条件**:

- 対象 family の new event records が `summary_key` と `render_params` だけで再レンダリングできる。
- 旧 save / old records は description fallback で表示できる。
- `event_models.py::WorldEventRecord` の責務が validation / serialization / projection に肥大化し続けない。

### Phase 2-B: 自前 guard と外部ツールの役割棚卸し

**目的**: 自前 AST guard を Fantasy Simulator 固有の設計ルールに集中させ、一般的な lint / complexity / import boundary を
外部ツールへ寄せられるか判断する。

**作業**:

- 現行 guard rule を「ゲーム固有」「一般 lint」「import boundary」「complexity」に分類する。
- Ruff、import-linter、radon 等へ移せる候補を調査する。
- すぐ移行せず、まず dry-run plan と CI 影響を確認する。
- 移行する場合も、既存 `scripts/quality_gate.py` の UX を壊さない wrapper から始める。

**完了条件**:

- 自前 guard に残すべき固有ルールが明文化されている。
- 外部ツールへ移す候補と、移さない理由が記録されている。
- guard failure の説明が、今より追いやすくなっている。

### Phase 3: UI framework 前の headless contract 固定

**目的**: Textual 等の本格 TUI を入れる前に、UI が読む headless data contract を安定させる。

**作業**:

- `WorldDashboardView` 相当の view model を定義する。
- report / rumor / map / follow-up action を CLI 以外からも読める形にする。
- Rich shell は薄い layout / emphasis / input assist に留める。
- map / report / rumor の snapshot harness を維持し、表示差分を検知できるようにする。

**完了条件**:

- UI renderer が domain object を直接読み漁らず、view model 経由で描画できる。
- Textual 導入可否を判断する前に、CLI と Rich shell が同じ view model を共有できる。
- UI complexity override の一部が view model 抽出により削減される。

---

## 4. PR 分割案

| PR | 内容 | 変更種別 | リスク |
|---|---|---|---|
| TR-0 | 本計画の追加 | docs only | 低 |
| TR-1 | Python version ADR と告知計画 | docs / CI 方針のみ | 低 |
| TR-2 | Override ledger 追加 | docs / guard metadata | 低〜中 |
| TR-3 | Persistence inventory と fixtures 追加 | docs / tests | 中 |
| TR-4 | Serializer split | refactor | 中 |
| TR-5 | Hydrator split | refactor | 高 |
| TR-6 | Semantic event inventory | docs / tests | 低〜中 |
| TR-7+ | Event family ごとの semantic rendering 移行 | feature/refactor | 中 |
| TR-8 | Guard tooling 棚卸し | docs / scripts | 中 |
| TR-9 | Headless dashboard/report contract | view model / tests | 中 |

---

## 5. 計測指標

- `architecture_guard.json` overrides 数と、accepted / reducible / intentional の内訳
- `world_persistence.py` の complexity override 有無
- semantic rendering 対応済み event family 数
- focused mypy target に入っている新規 split module 数
- save/load backward fixture 数
- UI renderer が直接参照する domain object の数

---

## 6. 着手順の推奨

この順序は技術レビュー由来の負債削減ストリーム内の推奨であり、公式 mainline milestone である PR-K の
実装順を上書きしない。

1. TR-1 と TR-2 を先に行い、version と debt ledger の意思決定基盤を作る。
2. TR-3 で persistence の fixture と payload inventory を固める。
3. TR-4 / TR-5 で serializer / hydrator を分割する。
4. TR-6 / TR-7+ で semantic event coverage を family 単位で広げる。
5. TR-8 は TR-2 の ledger 運用が安定してから着手する。
6. TR-9 は UI 改善の前提として進めるが、Textual 本格導入は引き続き保留する。

この順序なら、レビューが警告した「新技術で問題を隠す」方向へ逸れず、既存の強みである CLI、JSON migration、
Protocol-based UI abstraction、テスト / guardrail を活かして負債を減らせる。

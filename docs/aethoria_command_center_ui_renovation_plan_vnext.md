# Aethoria Command Center: UI Renovation Plan (vNext 統合版)

**プロジェクト名**: Fantasy Simulator  
**コンポーネント**: Aethoria System Terminal (Textual TUI Client)  
**版**: vNext-UI-Integration Draft 4 (Final/Contract-Refined)  
**位置づけ**: Fantasy Simulator vNext のプレイヤー体験（神の端末としての観察・介入）を実現するための、Textual ベース次世代 TUI 詳細設計。
**ステータス**: **RFC（提案）**。採用決定文書ではなく、実装前レビュー用の合意形成ドラフト。

> **整合性ルール**: 実装順序・公式着手対象・完了条件は `docs/implementation_plan.md` を正本とする。本書は UI 詳細設計であり、計画上の優先順位と衝突する場合は `docs/implementation_plan.md` を優先する。
>
> **現時点での適用範囲**: `docs/implementation_plan.md` では PR-I 完了後、PR-J / PR-K の前に TD-1〜TD-4 の負債解消を優先する。本書はその負債解消後に段階適用する Textual UI 契約案として扱う。
>
> **採用判断**: Textual は現時点で「評価候補」であり、正式採用は PoC と pilot テスト結果をもって別 PR / 別文書で決定する。

---

## 1. コンセプトと設計原則

### 1.1 中心体験への寄与

「自律的に生きる冒険者たちの世界を観察し、必要なときだけ介入する」体験を、**無機質で高度なシステム端末（コマンドセンター）**として表現する。空間（マップ）と時間（イベントストリーム）を同時に扱うテレメトリ監視体験へ昇華する。

### 1.2 UI Architecture Principles

- 情報のテレメトリ化: マップ直書きラベルを廃止し、記号中心で表示する
- 定性状態の可視化: 数値の生出しを避け、`serious`, `dying`, `declining` 等へ翻訳する
- セマンティック・ズーム: 縮尺で描画手法と着眼点（歴史/個人）を切り替える
- 非同期とストリーミング: 月次進行（時間）とカメラ操作（空間）を分離する
- i18n 徹底: UI 文字列はすべて `tr()` / `tr_term()` を経由する

> 補足: 数値は完全禁止ではなく、**UI 既定表示は label/band を正**とする。raw 数値は
> trend 判定・ソート・デバッグ・テストに限定した補助情報として扱う。

---

## 2. 既存システムとの統合（Phase 0: 制御反転）

現行の `main.py -> screens.py` は同期入力待ち（`ctx.choose_key()`）中心であり、Textual のイベント駆動に合わせて制御を反転する。

### 2.1 共存戦略

- CLI モード（既存）: `InputBackend` / `RenderBackend` による同期実行を維持
- TUI モード（新規）: Textual `App.run()` へ制御委譲
- 切替: 起動引数（例: `--ui textual`）または環境変数

### 2.2 反転後の制御フロー

- `TextualApp.compose()` で 3 ペイン構築
- `TextualApp.on_key()` で操作ディスパッチ（WASD, Zoom, Pause 等）
- シミュレーション進行は UI 入力と分離した worker thread で実行

---

## 3. レイアウト

- 上段左: `WORLD MATRIX`
- 上段右: `INSPECTOR`
- 下段: `EVENT STREAM`
- 操作フッタ: Quit / Step / Auto-Run / Pan / Zoom / Intervene

> モックの英語表記は説明用。実装では翻訳キー経由で解決する。

---

## 4. コンポーネント詳細

### 4.1 MapViewport

- カメラ座標・ズーム管理
- フォーカス座標に複数対象がある場合は内部でリスト保持
- `Tab` 等で Inspector 対象を切替

### 4.2 InspectorPanel

- Location: `danger_label`, alias, memorial, quest, rumor
- Character: 定性 health、`AdventureRun.policy`、`CharacterNarrativeState`、relationship

### 4.3 EventStreamLog

- Textual `RichLog` 使用
- `max_lines=500` で上限管理
- `WorldEventRecord` 由来の表示ストリーム

### 4.4 既存 `MapRenderInfo` / view model 接続方針

- **再利用優先**: 既存の `ui/map_renderer.py` にある `MapRenderInfo` / `MapCellInfo` と、
  `ui/view_models.py` のイベント・通知 view model を first-class な入力源として扱う。
- **段階移行**:
  1. Phase 1 は `MapRenderInfo` を直接 `MapViewportSnapshot` へ写像する adapter を追加する
  2. 既存 CLI 描画（ASCII / atlas）と Textual 描画は同じ source DTO を共有する
  3. domain 層（`World`, `Simulator`）に Textual 固有依存を持ち込まない
- **互換性原則**: `MapViewportSnapshot` は `MapRenderInfo` 置換ではなく UI transport DTO。
  canonical な world 参照経路と既存 renderer テストを壊さない。

---

## 5. イベントループとスレッドセーフティ

### 5.1 Worker モード

- Step: 1 ヶ月進行
- Auto-Run: 介入要求が発生するまで進行

```python
@work(thread=True)
def step_one_month(self):
    self.simulator.advance_months(1)
    snapshot = self.create_ui_snapshot()
    self.post_message(SimulationAdvancedEvent(snapshot, months_advanced=1))

@work(thread=True)
def run_simulation_auto(self):
    result = self.simulator.advance_until_pause()
    if result.get("pause_reason"):
        self.post_message(PauseRequiredEvent(result["pause_context"]))
    snapshot = self.create_ui_snapshot()
    self.post_message(
        SimulationAdvancedEvent(snapshot, months_advanced=result.get("months_advanced", 0))
    )
```

### 5.2 スナップショット戦略

- UI スレッドは live world を直接参照しない
- 月次進行完了時に描画用 immutable DTO を生成
- `SimulationAdvancedEvent` に添付して UI に受け渡す

### 5.3 並行実行規約（single-flight / cancel / stale snapshot）

- **single-flight**: Step / Auto-Run worker は同時に 1 本のみ実行可。
  実行中に次の進行要求が来た場合は reject し、UI に busy 状態を返す。
- **cancel**: Auto-Run はユーザー操作（Pause / Quit / Intervene）で cancel 要求可能とし、
  cancel は「次の安全停止点（月末）」で反映する。
- **stale snapshot 防止**:
  - `run_id`（単調増加）を worker 起動時に採番し、`SimulationAdvancedEvent` に含める
  - UI は最新 `run_id` 未満の snapshot を破棄する
  - `PauseRequiredEvent` と `SimulationAdvancedEvent` は同一 `run_id` で関連づける
- **UI 操作の独立**: カメラ移動や Inspector フォーカス変更は simulation worker と独立し、
  last known snapshot 上で完結させる。

---

## 6. 点字レンダリング仕様（Zoom OUT）

- 点字 1 文字 = 横 2 ドット × 縦 4 ドット
- `WorldGrid` の 2x4 セルを 1 文字へ圧縮
- 2値化
  - 1: `mountain`, `forest`, `settlement`
  - 0: `sea`, `plains`
- 各ドットのビット合算を `U+2800` に加算して文字化

---

## 7. UI 制約

- 最低ターミナルサイズ: 120x35
- マップ内の絵文字は不使用（幅差異を回避）
- EventStream の強調は Rich タグ経由
- UI 状態（カメラ・ズーム）は save/load JSON に含めない
- ロード時は world center + Zoom OUT で開始

### 7.1 狭幅端末 degradation policy

- **Tier-Full（120x35 以上）**: 3 ペイン完全表示（WORLD MATRIX / INSPECTOR / EVENT STREAM）
- **Tier-Compact（100x30 以上）**:
  - EVENT STREAM を高さ圧縮（直近 N 件のみ）
  - INSPECTOR を要約表示（詳細行を折りたたみ）
  - マップは主要 POI 記号のみ維持
- **Tier-Minimal（80x24 以上）**:
  - 単一ペイン切替（Map / Inspector / Event をタブ切替）
  - 点字レンダリング無効、ASCII 最小表示へフォールバック
  - Auto-Run 中はメトリクスを 1 行ステータスへ集約
- **Below-Minimum（80x24 未満）**:
  - 操作不能状態のまま描画継続しない
  - 「端末サイズを拡大してください」オーバーレイを表示し、進行入力を停止する

---

## 8. 実装フェーズとテスト

### Phase 0: 制御反転基盤

- `textual_app.py` 新設
- 3 ペイン骨格 + Worker 進行 + Pause 停止
- pilot: 起動 → SPACE で 1 ヶ月進行 → Quit

### Phase 1: 基本観測移植（`_show_results` 相当）

- `create_ui_snapshot()` 実装
- `map_renderer.py` / `view_models.py` 再利用で表示
- pilot: スナップショット更新テスト

### Phase 2: 自動進行と介入

- `advance_until_pause()` を Worker 接続
- `InterventionModal` 実装
- Zoom OUT 点字レンダラ導入
- テスト: pause → modal → 再開フロー、点字変換ユニット

### Phase 3: ナラティブ統合

- `scars`, `vows`, `dying` などを Inspector へ接続
- 残存同期画面を Textual タブ/モーダルへ段階移植
- テスト: フォーカス移動時の Inspector 差替え、詳細画面表示

---

## 9. UI Snapshot Contract

### 9.0 契約境界（locale / numeric）

- 本契約の snapshot は **locale 非依存 DTO** を基本とし、UI スレッドで `tr()` / `tr_term()` 解決する。
- `*_key` / `*_args` 形式を原則とし、raw string は互換移行中の暫定表現としてのみ許容する。
- Location 系メトリクスは `*_band` / `*_labels` を正規表示値とし、`int` は内部補助値とみなす。
- 将来互換のため、raw string フィールドは段階的に `*_key` へ寄せる（Phase 2-3 で完了目標）。

```python
from dataclasses import dataclass
from typing import Optional, Dict, Tuple, List, Union

@dataclass(frozen=True)
class EventStreamItemVM:
    year: int
    month: int
    category: str
    message_key: str
    message_args: dict
    severity: str  # info|warning|critical

@dataclass(frozen=True)
class PendingChoiceOptionVM:
    action_id: str
    label_key: str
    label_args: dict
    emphasis: str  # primary|danger|default

@dataclass(frozen=True)
class PendingChoiceVM:
    choice_id: str
    actor_name: str
    reason: str
    description_key: str
    options: List[PendingChoiceOptionVM]

@dataclass(frozen=True)
class LocationInspectorSnapshot:
    target_name: str
    state_labels: List[str]
    traffic_band: str          # UI 正規表示 (low|moderate|high|critical)
    danger_band: str           # UI 正規表示 (safe|uneasy|dangerous|deadly)
    traffic_value: int         # 内部補助値（既定で非表示）
    danger_value: int          # 内部補助値（既定で非表示）
    live_trace_keys: List[str]
    rumor_keys: List[str]

@dataclass(frozen=True)
class CharacterInspectorSnapshot:
    target_name_key: str
    health_state: str          # enum key: healthy|injured|serious|dying
    policy_key: str
    scar_keys: List[str]
    vow_keys: List[str]
    relationship_keys: List[str]

InspectorSnapshot = Union[LocationInspectorSnapshot, CharacterInspectorSnapshot]

@dataclass(frozen=True)
class MapViewportSnapshot:
    grid_width: int
    grid_height: int
    terrain_grid: List[List[str]]
    poi_markers: Dict[Tuple[int, int], str]  # marker symbol itself (locale independent)
    inspector_data: Dict[Tuple[int, int], List[InspectorSnapshot]]

@dataclass(frozen=True)
class DashboardSnapshot:
    year: int
    month: int
    map_view: MapViewportSnapshot
    new_events: List[EventStreamItemVM]
    pending_choice: Optional[PendingChoiceVM] = None
```

---

## 10. 既存文書との整合性チェック結果

本ドラフトは以下の点で既存文書と整合する。

1. **制御反転の方向性**: 現行同期 UI（`choose_key`）を維持しつつ新規 Textual を共存させる方針は、既存の UI backend 抽象化方針と一致する。  
2. **正規イベント源**: Event Stream を `WorldEventRecord` 起点で扱う点は、実装計画書の canonical 方針と一致する。  
3. **i18n 方針**: `tr()` / `tr_term()` 経由を必須化しており、既存規約と一致する。  
4. **段階移行**: 一括置換ではなく Phase 分割で移行するため、既存の段階導入原則と一致する。  
5. **優先順位の扱い**: 本書は RFC（提案）であり、実装順序の最終判断は `docs/implementation_plan.md` 優先と明記済み。  
6. **DTO 境界**: locale 非依存 snapshot + UI 側翻訳解決を原則化し、既存 i18n 方式と矛盾しない。

# Aethoria Command Center: UI Renovation Plan (vNext 統合版)

**プロジェクト名**: Fantasy Simulator  
**コンポーネント**: Aethoria System Terminal (Textual TUI Client)  
**版**: vNext-UI-Integration Draft 4 (Final/Contract-Refined)  
**位置づけ**: Fantasy Simulator vNext のプレイヤー体験（神の端末としての観察・介入）を実現するための、Textual ベース次世代 TUI 詳細設計。

> **整合性ルール**: 実装順序・公式着手対象・完了条件は `docs/implementation_plan.md` を正本とする。本書は UI 詳細設計であり、計画上の優先順位と衝突する場合は `docs/implementation_plan.md` を優先する。
>
> **現時点での適用範囲**: `docs/implementation_plan.md`（2026-03-31 時点）で次の公式着手対象は PR-I（NarrativeContext 拡張）。本書は PR-I 以降に段階適用する Textual UI 契約案として扱う。

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
    traffic: int
    danger: int
    live_traces: List[str]
    rumors: List[str]

@dataclass(frozen=True)
class CharacterInspectorSnapshot:
    target_name: str
    health_state: str
    policy: str
    scars: List[str]
    vows: List[str]
    relationships: List[str]

InspectorSnapshot = Union[LocationInspectorSnapshot, CharacterInspectorSnapshot]

@dataclass(frozen=True)
class MapViewportSnapshot:
    grid_width: int
    grid_height: int
    terrain_grid: List[List[str]]
    poi_markers: Dict[Tuple[int, int], str]
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
5. **優先順位の扱い**: 本書は「詳細設計」であり、実装順序の最終判断は `docs/implementation_plan.md` 優先と明記済み。


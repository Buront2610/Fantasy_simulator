# TD-3 Design Decisions (world/events split)

最終更新: 2026-04-16

## 1) Removed legacy fields in `WorldEventRecord`

**Decision**: `legacy_event_result` / `legacy_event_log_entry` は
`WorldEventRecord` から削除する。旧 save の入力に含まれていても
migration / load boundary で canonical fields へ吸収し、現行保存には再出力しない。

**理由**:
- canonical-first ではなく canonical-only に寄せ、保存・表示・計測の分岐を減らすため。
- event-log projection は canonical fields からのみ生成する。
- 旧 payload の exact projection は捨て、旧データは `description` / actor / kind / date
  など現行 record fields へ持ち上げる。

## 2) Import surface (`events.py` vs `event_models.py`)

**Decision**: 新規実装は `event_models.py` を正規参照とし、`events.py` は互換 facade として維持する。

**ルール**:
- 新規の型参照 (`EventResult`, `WorldEventRecord`, `generate_record_id`) は `event_models.py` を直接 import する。
- 既存コード・外部利用者向けに `events.py` の re-export (`__all__`) は維持する。

## 3) Contract style (`normalize` vs `fail-fast`)

**Decision**: 境界ごとに使い分ける。

- 構造欠落（必須キー欠落など）: fail-fast
- 値域逸脱（月/日/severity 等）: normalize

この方針は `event_models.py` 冒頭 docstring とテストで固定する。

## 4) Mutable payload handling in `to_dict` / `from_dict`

**Decision**: defensive copy を採用する。

- nested dict/list を shallow 共有せず、`deepcopy` で返却。
- 呼び出し側の破壊的編集がモデル内部へ漏れないことをテストで保証する。


## 5) Legacy concern retreat plan

**Decision**: legacy payload は persisted field として保持しない。

**Boundary prep**:
- canonical path は `kind/year/month/day/...` + `impacts/tags` を正とする。
- compatibility event log は canonical projection のみを利用する。

## 6) Impact / propagation rule externalization prep

**Decision**: helper API を `rules` 引数受け取りへ拡張し、setting bundle から注入可能にした。

**Current state**:
- `WorldDefinition` に `event_impact_rules` / `propagation_rules` を追加し、
  `World` が active bundle から rules を読み込み helper に渡す。
- helper 側は bundled default rules を fallback として保持する。

**Roadmap extension (PR-K 前提)**:
- era/faction modifier を rule evaluator の入力として注入可能にする。

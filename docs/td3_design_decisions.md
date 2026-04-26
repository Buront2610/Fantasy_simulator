# TD-3 Design Decisions (world/events split)

最終更新: 2026-04-16

## 1) Legacy fields in `WorldEventRecord`

**Decision**: `legacy_event_result` / `legacy_event_log_entry` は
`WorldEventRecord` の optional compatibility payload として保持する。

**理由**:
- canonical-first の event record を主に保ちつつ、older saves の backward-load
  compatibility と legacy adapter の exact projection を維持するため。
- runtime の互換 adapter (`Simulator.history`, compatibility log formatter) は
  canonical fields を優先しつつ、必要な場合のみ persisted compatibility payload を使う。

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

**Decision**: legacy payload は canonical-first record に付随する optional
compatibility field として限定保持する。

**Boundary prep**:
- canonical path は `kind/year/month/day/...` + `impacts/tags` を正とする。
- legacy adapter (`Simulator.history`, compatibility event log) は canonical
  projection を基本としつつ、migrated save の backward-load compatibility を守る
  ため persisted compatibility payload も利用してよい。

## 6) Impact / propagation rule externalization prep

**Decision**: helper API を `rules` 引数受け取りへ拡張し、setting bundle から注入可能にした。

**Current state**:
- `WorldDefinition` に `event_impact_rules` / `propagation_rules` を追加し、
  `World` が active bundle から rules を読み込み helper に渡す。
- helper 側は bundled default rules を fallback として保持する。

**Roadmap extension (PR-K 前提)**:
- era/faction modifier を rule evaluator の入力として注入可能にする。

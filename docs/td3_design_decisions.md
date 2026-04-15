# TD-3 Design Decisions (world/events split)

最終更新: 2026-04-15

## 1) Legacy fields in `WorldEventRecord`

**Decision**: 当面は `legacy_event_result` / `legacy_event_log_entry` を `WorldEventRecord` に残す。

**理由**:
- save/load 互換維持が最優先。
- `Simulator.history` / `World.get_compatibility_event_log()` の既存アダプタが即時に利用可能。
- sunset は TD-1 の保存フォーマット縮退バッチ（PR-J/K 前）で実施する。

**Exit criteria**:
- 互換アダプタが persistence に依存しなくなった時点で adapter 層へ移管。

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

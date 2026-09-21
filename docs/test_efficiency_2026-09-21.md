# 検証の重複と地図生成コストの削減

検証対象・判定基準・Hypothesisの200ms制限を維持して、同じ処理の繰り返しを減らした。
CI設定、保存スキーマ、ゲームバランス、ランタイム依存は変更していない。

## 変更

- `strict` / `exhaustive` はlintと複雑度を一度のflake8呼び出しで検査する。
  `--max-complexity=25` は通常のlint診断に複雑度診断を追加する。
  実際にE501・F821・C901を含む入力を拒否する回帰試験を追加した。
- `standard` / `strict` の追加指定テストと標準テストを一つのpytestプロセスで実行し、
  同一のセレクターは一度だけ渡す。異なるセレクターが同じテストを指す場合までの自動推論は行わない。
- 品質ゲートの開始表示を即座にflushし、長い処理中もどの段階かを確認できるようにした。
- 地図生成の輪郭判定で、数学的に陸地になり得ないセルの三角関数計算を省いた。
  閾値の最大値は1.66なので、正規化半径2の外側を除外しても結果は変わらない。
- 新しく生成した地図のコンテナを、直後にデシリアライズして複製する処理を省いた。
  既存オブジェクトのロード時の防御的コピーは維持し、生成した別世界間で変更が漏れないことを確認した。
- 旧セーブに地図が存在するとき、`setdefault`の引数評価で不要な地図を生成しない。
  サイト座標の補完は従来どおり行う。

## ローカル計測

| 対象 | 変更前 | 変更後 | 差 |
|---|---:|---:|---:|
| 変更ソース一式のlint＋複雑度、2回ずつの平均 | 8.02秒 | 4.09秒 | 約49%短縮 |
| v0移行＋出力ハッシュ照合、3組×5回の中央値/回 | 541ms | 235ms | 約57%短縮 |

lintはbefore/after/after/beforeの順で、同じファイルを対象に実行した。
移行は同じプロセスでbefore/afterを交互に切り替え、完全な出力ハッシュの一致も検証した。
移行の数値にはJSON化とハッシュ照合を含み、Hypothesisが測るテスト本体だけの時間とは異なる。
マシン負荷による変動があるため、全テストや他環境で同率の短縮を保証するものではない。

3種類の完全な地図ペイロード、30組の固定乱数によるクラスタ・経路、
完全なv0→現行スキーマ移行結果が変更前と一致した。
変更前に時間制限で失敗した移行プロパティテストは、制限を変更せず関連37テストとともに成功した。
テストの削除、skip追加、健康バンドや複雑度閾値の緩和は行っていない。

## 最終検証

- 関連209テストが346.18秒で成功。品質ゲート、地図出力の同値性、プロパティ、冒険の健康状態、
  terrainとその統合、移行、保存・読込契約、構造チェック、エージェント運用ドキュメントを対象とした。
- 全ソースのlint＋複雑度チェックが成功。設定された166ソースのmypyも成功。
- 検証中はソースを固定し、終了後の変更はこの検証記録のみ。
- 今回、約2000件の全テスト一式は再実行していない。全体の実行時間短縮率は未計測。

関連テストの再現コマンド:

```console
python -m pytest tests/test_quality_gate.py tests/test_atlas_generation_equivalence.py tests/test_properties.py tests/test_adventure_health.py tests/test_terrain.py tests/test_terrain_integration.py tests/test_migrations.py tests/test_save_load.py tests/test_pr_k_save_contracts.py tests/test_architecture_guard.py tests/test_agent_workflow_docs.py --durations=12 -q
```

全静的検査の再現コマンド:

```console
python -c "from scripts.quality_gate import build_profile_commands,run_commands; raise SystemExit(run_commands(build_profile_commands('exhaustive')[:-1]))"
```

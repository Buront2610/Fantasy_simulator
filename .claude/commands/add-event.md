新しいイベントタイプをシミュレーションに追加してください。

イベント名: $ARGUMENTS

以下の手順で実装してください:

1. `events.py` を読んで既存のイベント構造を理解する
2. `i18n.py` を読んで翻訳キーの命名規則を確認する
3. 新しいイベントの実装:
   - `events.py` にイベント生成ロジックを追加
   - `i18n.py` の `_TEXT` / `_TERMS` に英語・日本語の翻訳文字列を追加（`tr()` / `tr_term()` で参照）
4. `tests/test_events.py` にテストを追加
5. `flake8 --max-line-length=120 --exclude=node_modules,__pycache__ .` でLintチェック
6. `python -m pytest tests/test_events.py -v` でテスト実行
7. 問題があれば修正

既存のイベント（meeting, journey, discovery, training, battle）のパターンに合わせて実装すること。

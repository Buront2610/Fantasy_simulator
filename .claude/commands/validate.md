Lint + テストを一括実行して結果を報告してください。

1. まず `flake8 --max-line-length=120 --exclude=node_modules,__pycache__,.claude,.worktrees .` を実行
2. 次に `python -m pytest tests/ -v` を実行
3. 結果をまとめて報告:
   - Lintエラーがあれば一覧表示
   - テスト結果（pass/fail数）
   - 失敗したテストがあれば詳細を表示
4. 問題があれば修正案を提示（自動修正はしない）

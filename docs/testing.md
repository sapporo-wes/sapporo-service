# Testing Guide

## テストの実行

```bash
# 全テスト実行
uv run pytest

# verbose 出力
uv run pytest -v

# 特定ファイル
uv run pytest tests/unit/test_utils.py

# 特定テスト
uv run pytest tests/unit/test_utils.py::test_str2bool_with_true_string_returns_true

# ランダム順序で実行（順序依存のチェック）
uv run pytest -p randomly -v

# slow マーカーを除外
uv run pytest -m "not slow"
```

## Mutation Testing

```bash
# pyproject.toml の [tool.mutmut] 設定に従って実行
uv run mutmut run

# 結果確認
uv run mutmut results

# survived mutant の詳細
uv run mutmut show <mutant_id>
```

### 既知の制限

mutmut v3 はソースファイルを `mutants/` ディレクトリにコピーして変異を適用する。
`sapporo/config.py` のように `Path(__file__)` でデータファイルを解決するモジュールは、
コピー先にデータファイルが存在しないためエラーになる。
現在は `sapporo/utils.py` と `sapporo/exceptions.py` のみを対象としている。

## テスト構造

```
tests/unit/
  conftest.py         -- 共通フィクスチャとヘルパー
  test_utils.py       -- sapporo/utils.py のテスト（PBT 重点）
  test_exceptions.py  -- sapporo/exceptions.py のテスト
  test_schemas.py     -- sapporo/schemas.py のテスト（Pydantic バリデーション）
  test_config.py      -- sapporo/config.py のテスト（環境変数・CLI パース）
  test_auth.py        -- sapporo/auth.py のテスト（セキュリティ最重要）
  test_validator.py   -- sapporo/validator.py のテスト
  test_factory.py     -- sapporo/factory.py のテスト（FS 依存）
```

## テスト追加時の手順

1. 対象モジュールに対応する `test_<module>.py` にテストを追加
2. 命名規則: `test_<対象>_<条件>_<期待結果>()`
3. PBT が適用可能なら hypothesis の `@given` を使う
4. `uv run pytest -v` で PASS を確認
5. `uv run ruff check tests/` と `uv run ruff format --check tests/` でリントクリーンを確認
6. 必要に応じて `uv run mutmut run --paths-to-mutate sapporo/<module>.py` で検出力を検証

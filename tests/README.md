# Tests

## Philosophy

- テストは **バグを探す** ために書く。カバレッジは目標にしない
- TDD を意識し、実装前にテストを考える
- Property-Based Testing (PBT) で仕様の不変条件を検証する
- テスト間で状態を共有しない。実行順序に依存しない（pytest-randomly で検証）

## Mock Policy

Mock は **外部境界**（HTTP、DB、FS）だけに使う。内部実装を mock しない。

| 対象 | Mock | 理由 |
|------|------|------|
| HTTP リクエスト (httpx) | OK | 外部サービス依存 |
| DB (SQLModel) | OK | 外部状態 |
| FS (ファイル読み書き) | OK（`tmp_path` 推奨） | 外部状態 |
| `get_config()` | OK（例外） | 全モジュールが依存する設定読み込み。FS 読み込みに近い |
| 内部関数の振る舞い | NG | テストが実装詳細に依存する |

## Naming

- ファイル名: `test_<module>.py`
- 関数名: `test_<対象>_<条件>_<期待結果>()`
- 例: `test_str2bool_with_true_string_returns_true()`

## PBT Guide

[hypothesis](https://hypothesis.readthedocs.io/) を使って、手動テストでは見つけにくいエッジケースを検出する。

### 使いどころ

- **Round-trip property**: `decode(encode(x)) == x`
- **Security invariant**: 「出力に `..` を含まない」「`/` で始まらない」
- **No-crash property**: 任意入力で例外が発生しない

### Strategy パターン

```python
from hypothesis import given
import hypothesis.strategies as st

# 任意の文字列
@given(st.text())
def test_never_crashes(s: str) -> None:
    result = some_function(s)
    assert isinstance(result, str)

# 特定パターンの文字列
@given(st.from_regex(r"[a-zA-Z0-9_\-.@]{1,128}", fullmatch=True))
def test_valid_usernames(username: str) -> None:
    assert sanitize_username(username) == username
```

### セキュリティ不変条件の例

```python
@given(st.text())
def test_secure_filepath_no_parent_traversal(filepath: str) -> None:
    result = secure_filepath(filepath)
    for part in result.parts:
        assert ".." not in part

@given(st.text())
def test_secure_filepath_no_absolute_path(filepath: str) -> None:
    result = secure_filepath(filepath)
    assert not str(result).startswith("/")
```

## Mutation Testing

[mutmut](https://mutmut.readthedocs.io/) でテストの検出力を検証する。

### 実行方法

```bash
# 特定モジュールに対して実行
uv run mutmut run --paths-to-mutate sapporo/utils.py

# 結果確認
uv run mutmut results

# survived mutant の詳細
uv run mutmut show <mutant_id>
```

### Survived mutant の分析

survived mutant が見つかった場合：

1. `mutmut show <id>` で変異内容を確認
2. その変異が実際のバグに該当するか判断
3. 該当する場合 → テストを追加
4. 該当しない場合（等価変異など） → スキップ

## Directory Structure

```
tests/
  README.md          -- このファイル
  unit/
    conftest.py      -- フィクスチャとヘルパー
    test_utils.py
    test_exceptions.py
    test_schemas.py
    test_config.py
    test_auth.py
    test_validator.py
    test_factory.py
```

# Release Process

## Version Management

- `pyproject.toml` の `version` フィールドが唯一のバージョン定義
- ランタイムでは `importlib.metadata.version("sapporo")` で取得
- Docker イメージのバージョンは CI がタグ名から `--build-arg VERSION=...` で注入

## Release Steps

1. `develop` branch で `pyproject.toml` の `version` を更新し、`uv lock` を実行
2. `develop` → `main` の PR を作成してマージ
3. `main` branch にバージョンタグを作成:

   ```bash
   git checkout main && git pull
   git tag X.Y.Z
   git push origin X.Y.Z
   ```

4. タグ push で `release.yml` が自動実行:
   - バージョン整合性チェック (tag == pyproject.toml version)
   - PyPI パッケージの公開 (Trusted Publishing)
   - Docker マルチアーキテクチャイメージのビルド・push (ghcr.io)
   - GitHub Release の作成 (リリースノート自動生成)

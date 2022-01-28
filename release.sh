#!/usr/bin/env bash
set -euxo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <new_version>"
  exit 1
fi

PREV_VERSION=$(git describe --abbrev=0 --tags)
NEW_VERSION=$1

read -p "Does update version from $PREV_VERSION to $NEW_VERSION? (y/n) :" YN

if [[ "$YN" != "y" ]]; then
  echo "Aborted."
  exit 1
fi

NOW_BRANCH=$(git rev-parse --abbrev-ref HEAD)

if [[ "$NOW_BRANCH" != "main" ]]; then
  echo "You must be on main branch."
  git checkout main
fi

echo "Merge develop branch to main branch."
git merge develop

echo "Rewrite files."
sed -i "s/version=\"$PREV_VERSION\"/version=\"$NEW_VERSION\"/g" Dockerfile
sed -i "s/sapporo-service:$PREV_VERSION/sapporo-service:$NEW_VERSION/g" docker-compose.yml
sed -i "s/\"sapporo-version\": \"$PREV_VERSION\"/\"sapporo-version\": \"$NEW_VERSION\"/g" sapporo/service-info.json
sed -i "s/version=\"$PREV_VERSION\"/version=\"$NEW_VERSION\"/g" setup.py

echo "Commit and push."
git add Dockerfile docker-compose.yml sapporo/service-info.json setup.py
git commit -m "Update version to $NEW_VERSION"
git push origin main

echo "Tag and push."
git tag $NEW_VERSION
git push origin $NEW_VERSION

echo "Merge main branch to develop branch."
git checkout develop
git merge main
git push origin develop

echo "Done."
exit 0

#!/usr/bin/env bash
set -e

VERSION=${1:-}

if [[ -z "$VERSION" ]]; then
    echo "Usage: ./release.sh <version>  (e.g. ./release.sh 1.6.1)"
    exit 1
fi

TAG="v$VERSION"

if git rev-parse "$TAG" >/dev/null 2>&1; then
    echo "Tag $TAG already exists."
    exit 1
fi

git tag "$TAG"
git push origin "$TAG"

echo "Tagged and pushed $TAG — release workflow triggered."

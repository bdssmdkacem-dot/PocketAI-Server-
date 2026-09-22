#!/usr/bin/env bash
set -euo pipefail

LLAMA_REPO="https://github.com/ggml-org/llama.cpp.git"
LLAMA_COMMIT="f95b0d95394d5e311ba8228689972843178c5e28"
TARGET="third_party/llama.cpp"

rm -rf "$TARGET"
mkdir -p "$(dirname "$TARGET")"

git init "$TARGET"
git -C "$TARGET" remote add origin "$LLAMA_REPO"
git -C "$TARGET" fetch --depth 1 origin "$LLAMA_COMMIT"
git -C "$TARGET" checkout --detach "$LLAMA_COMMIT"

echo "llama.cpp pinned to $(git -C "$TARGET" rev-parse HEAD)"

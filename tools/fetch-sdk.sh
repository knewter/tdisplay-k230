#!/usr/bin/env bash
# Fetch the upstream LilyGO RT-Smart SDK (~2.5 GB) into ./repo, gitignored.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d repo ] && { echo "repo/ already present"; exit 0; }
git clone --depth 1 https://github.com/Xinyuan-LilyGo/T-Display-K230_canmv_rt.git repo

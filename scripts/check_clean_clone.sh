#!/usr/bin/env bash
# Clone the committed HEAD into a temp dir and run make setup check there.
# Uncommitted changes are not included: commit first.
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

git clone --quiet "$root" "$tmp/repo"
cd "$tmp/repo"
echo "clean clone of $(git rev-parse --short HEAD) in $tmp/repo"
"${MAKE:-make}" setup check
echo "clean clone: OK"

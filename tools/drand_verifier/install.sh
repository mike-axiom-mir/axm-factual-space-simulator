#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"
npm ci --ignore-scripts --no-audit --no-fund
node verify.mjs </dev/null >/dev/null 2>&1 || true
printf '%s\n' 'Pinned AXM drand verifier dependencies installed.'

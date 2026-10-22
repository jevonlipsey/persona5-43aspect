#!/bin/bash
# One-time: import original/P5R.exe into analysis/ghidra (no auto-analysis).
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
GH=${GHIDRA:-/opt/homebrew/opt/ghidra/libexec/support/analyzeHeadless}
export JAVA_HOME=${JAVA_HOME:-$(/usr/libexec/java_home 2>/dev/null || true)}
mkdir -p "$ROOT/analysis/ghidra"
rm -rf "$ROOT/analysis/ghidra/P5R.gpr" "$ROOT/analysis/ghidra/P5R.rep"
"$GH" "$ROOT/analysis/ghidra" P5R -import "$ROOT/original/P5R.exe" -noanalysis 2>&1 \
  | tee "$ROOT/analysis/ghidra/setup.log" | tail -20

#!/bin/bash
# usage: tools/ghidra/decomp.sh <rva-hex>...   -> analysis/decomp/sub_<rva>.c
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
GH=${GHIDRA:-/opt/homebrew/opt/ghidra/libexec/support/analyzeHeadless}
export JAVA_HOME=${JAVA_HOME:-$(/usr/libexec/java_home 2>/dev/null || true)}
"$GH" "$ROOT/analysis/ghidra" P5R -process P5R.exe -noanalysis -readOnly \
  -scriptPath "$ROOT/tools/ghidra" -postScript Decomp.java "$ROOT/analysis/decomp" "$@" 2>&1 \
  | grep -E "Decomp.java>|ERROR|Exception" | sed 's/^INFO  Decomp.java> //; s/ (GhidraScript)$//'

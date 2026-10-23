#!/usr/bin/env bash
# builds the browser patcher into web/dist/ (a static site). run from the repo root:
#   tools/build_web.sh
# pure JavaScript: the patch table and known hashes are generated from tools/p5r_patch.py.
set -euo pipefail

cd "$(dirname "$0")/.."

DIST=web/dist
rm -rf "$DIST"
mkdir -p "$DIST"

echo "[+] generating web/app/patches.js from tools/p5r_patch.py --json"
# if original/P5R.exe exists locally, use it; otherwise generate from cached header + known hash
if [ -f "original/P5R.exe" ]; then
  python3 tools/p5r_patch.py --json original/P5R.exe web/app/patches.js --set fit43,cam43,film43
else
  python3 tools/gen_web_data.py web/app/patches.js
fi

for f in index.html style.css main.js patcher-runtime.js patches.js; do
  cp "web/app/$f" "$DIST/$f"
done

touch "$DIST/.nojekyll"

echo "[+] web/dist ready"
for f in patches.js patcher-runtime.js main.js index.html style.css; do
  echo "    $f: $(wc -c < "$DIST/$f" | awk '{printf "%.1f KB", $1/1024}')"
done
echo "    total:      $(du -sk "$DIST" | cut -f1) KB"

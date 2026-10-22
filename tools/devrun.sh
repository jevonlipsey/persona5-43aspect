#!/bin/bash
# One device test run of a patched P5R.exe. usage: tools/devrun.sh <exe> <label> [seconds]
# Takes the shared device lock (waits), backs up settings, deploys with hash check, launches via
# ddlaunch (never the Linux Steam client), screenshots every 15 s into shots/<label>/, kills only
# the new processes, puts the pristine exe back live, releases the lock.
set -u
EXE=$1; LABEL=$2; SECS=${3:-240}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/shots/$LABEL"; mkdir -p "$OUT"
G=/mnt/droiddeck-sd/steamapps/common/P5R
PFX=/mnt/droiddeck-sd/steamapps/compatdata/1687950/pfx/drive_c/users/steamuser/AppData/Roaming/SEGA/P5R
PRIST=5d9e18c383700302d029c947ddf8c811ba6afa47e60ec1afa0554d452bdc0cbf
S="ssh -o BatchMode=yes droiddeck"
adb forward tcp:2222 tcp:2222 >/dev/null 2>&1
for i in $(seq 1 120); do
  $S "mkdir /tmp/nova-43aspect.lock 2>/dev/null && echo 'persona5-43aspect $(date +%s)' > /tmp/nova-43aspect.lock/owner" && break
  echo "lock held: $($S 'cat /tmp/nova-43aspect.lock/owner')"; sleep 60
done
$S 'test -d /tmp/nova-43aspect.lock' || { echo no lock; exit 1; }
trap '$S "rm -rf /tmp/nova-43aspect.lock"' EXIT
if $S "pgrep -f 'gamescope|wineserver' | grep -v \$\$ | head -1" | grep -q .; then echo "a game is running; abort"; exit 2; fi
$S "pgrep -fa 'gamescope|droiddeck-gpu|wineserver|P5R' | grep -v pgrep | awk '{print \$1}'" | sort > "$OUT/pids.before"
# backup settings/saves (small)
$S "cd '$PFX' && tar cf /mnt/droiddeck-sd/p5r-save-backup-$LABEL.tar . 2>&1 | tail -1; ls -la /mnt/droiddeck-sd/p5r-save-backup-$LABEL.tar"
$S "test -f '$G/P5R.exe.pristine' || cp -p '$G/P5R.exe' '$G/P5R.exe.pristine'; sha256sum '$G/P5R.exe.pristine'" | tee "$OUT/pristine.sha"
grep -q $PRIST "$OUT/pristine.sha" || { echo "pristine hash mismatch"; exit 3; }
L=$(shasum -a 256 "$EXE" | cut -d' ' -f1)
$S "cat > '$G/P5R.exe.new'" < "$EXE"
R=$($S "sha256sum '$G/P5R.exe.new'" | cut -d' ' -f1)
[ "$L" = "$R" ] || { echo "upload hash mismatch"; $S "rm -f '$G/P5R.exe.new'"; exit 4; }
$S "mv '$G/P5R.exe.new' '$G/P5R.exe'"
echo "deployed $L"
pid=$($S 'pgrep -n konsole || pgrep -n lxqt-panel')
$S "python3 /root/ddlaunch.py $pid /usr/local/bin/droiddeck-gpu /usr/local/bin/droiddeck-proton-run --app 1687950"
t=0
while [ $t -lt $SECS ]; do
  sleep 15; t=$((t+15))
  adb -s 6f1b78cc exec-out screencap -p > "$OUT/s$(printf %03d $t).png"
done
$S "tail -40 /tmp/ddlaunch.log" > "$OUT/ddlaunch.log"
$S "pgrep -fa 'gamescope|droiddeck-gpu|wineserver|P5R|steam.exe|winedevice|services.exe|svchost|rpcss|explorer.exe|plugplay|tabtip' | grep -v pgrep | awk '{print \$1}'" | sort > "$OUT/pids.after"
NEW=$(comm -13 "$OUT/pids.before" "$OUT/pids.after" | tr '\n' ' ')
echo "new pids: $NEW"
$S "kill $NEW 2>/dev/null; sleep 10; kill -9 $NEW 2>/dev/null; true"
sleep 3
$S "pgrep -fa 'gamescope|P5R|wineserver' | grep -v pgrep" 
# restore pristine live
$S "cp -p '$G/P5R.exe.pristine' '$G/P5R.exe.restore' && mv '$G/P5R.exe.restore' '$G/P5R.exe'; sha256sum '$G/P5R.exe'"
echo done

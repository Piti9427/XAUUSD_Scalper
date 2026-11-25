#!/bin/bash
# MT5 access-point watchdog v2 (Exness DEMO). Clicks "Access Point #1" in MT5 connection menu
# when c22-selected-execution reports algo_permissions_required persistently.
# Never restarts services, never trades. Usage: mt5_ap_watchdog.sh [--dry-run]
# Detection:
#   normal : each of last 2x60s slices has >=20% algo_permissions_required ticks (and >=2)
#   fast   : (terminal started <10min ago, or within 20 min after a 00/06/12/18 UTC scan)
#            each of last 3x30s slices has >=1 algo_permissions_required tick (~90s of loop)
# Before the first click of an episode, runs mt5_ap_capture.sh (read-only, max once/6h).
set -u
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
ST=/home/ubuntu/c22-demo/state
OPS=/home/ubuntu/c22-demo/ops-local
LOG=$ST/mt5-ap-watchdog.log
SHOTS=$ST/mt5-ap-watchdog-shots
ATT=$ST/mt5-ap-watchdog.attempts
FLAG=$ST/mt5-ap-watchdog.DISABLED
NOCAP=$ST/mt5-ap-capture.DISABLED
MAXH=4
RATIO_PCT=20
IND_X=1238; IND_Y=1014; AP1_X=1110; AP1_Y=848
mkdir -p "$SHOTS"; touch "$ATT"
log(){ echo "$(date -u +%FT%TZ) [$([ $DRY = 1 ] && echo DRY || echo LIVE)] $*" >> "$LOG"; }
exec 9>/tmp/mt5-ap-watchdog.lock; flock -n 9 || exit 0

reasons(){ journalctl -u c22-selected-execution --since "$1" --until "$2" --no-pager -o cat 2>/dev/null | grep -o '"reason": "[a-z_]*"' | sed 's/.*: "//;s/"//'; }
bad_in(){ reasons "$1" "$2" | grep -c '^algo_permissions_required$'; }
good_in(){ reasons "$1" "$2" | grep -vc '^algo_permissions_required$'; }

MODE=normal
st=$(systemctl show c22-selected-terminal -p ActiveEnterTimestamp --value)
stsec=$(date -d "$st" +%s 2>/dev/null || echo 0); nowsec=$(date +%s)
[ $((nowsec - stsec)) -lt 600 ] && MODE=fast-startup
h=$(date -u +%-H); m=$(date -u +%-M)
[ $((h % 6)) -eq 0 ] && [ "$m" -lt 20 ] && MODE=fast-scan

is_stuck(){
  if [ "$MODE" = normal ]; then
    local b1 t1 b2 t2
    b1=$(bad_in -120s -60s); t1=$(( b1 + $(good_in -120s -60s) ))
    b2=$(bad_in -60s now);   t2=$(( b2 + $(good_in -60s now) ))
    STATS="mode=$MODE bad/total 60s slices(old->new)=$b1/$t1 $b2/$t2"
    [ "$b1" -ge 2 ] && [ "$b2" -ge 2 ] && [ $((b1*100)) -ge $((t1*RATIO_PCT)) ] && [ $((b2*100)) -ge $((t2*RATIO_PCT)) ]
  else
    local a b c
    a=$(bad_in -90s -60s); b=$(bad_in -60s -30s); c=$(bad_in -30s now)
    STATS="mode=$MODE bad 30s slices(old->new)=$a/$b/$c other_last60s=$(good_in -60s now)"
    [ "$a" -gt 0 ] && [ "$b" -gt 0 ] && [ "$c" -gt 0 ]
  fi
}
if ! systemctl is-active -q c22-selected-execution; then [ $DRY = 1 ] && log "execution service not active"; exit 0; fi
if ! is_stuck; then
  [ $DRY = 1 ] && log "healthy ($STATS); no action"
  exit 0
fi
log "STUCK detected: $STATS"
if [ -e "$FLAG" ]; then log "disabled flag $FLAG present; not acting"; exit 0; fi
now=$(date +%s); awk -v n=$now '$1>n-3600' "$ATT" > "$ATT.tmp"; mv "$ATT.tmp" "$ATT"
cnt=$(wc -l < "$ATT")
if [ "$cnt" -ge $MAXH ]; then log "rate limit: $cnt attempts in last hour; writing $FLAG and stopping (rm it to re-enable)"; date -u +%FT%TZ > "$FLAG"; exit 0; fi

XP=$(pgrep -f 'xvfb-run.*terminal64\.exe' | head -1)
XL=$(ps -o args= --ppid "$XP" 2>/dev/null | grep '^Xvfb' | head -1)
DISP=$(echo "$XL" | grep -o ' :[0-9]*' | head -1 | tr -d ' ')
AUTH=$(echo "$XL" | sed -n 's/.*-auth \([^ ]*\).*/\1/p')
if [ -z "$DISP" ] || [ -z "$AUTH" ]; then log "could not discover MT5 Xvfb (xvfb-run pid=$XP line=$XL)"; exit 1; fi
export DISPLAY=$DISP XAUTHORITY=$AUTH
ts=$(date -u +%Y%m%dT%H%M%SZ)
log "MT5 display=$DISP auth=$AUTH"
if [ $DRY = 1 ]; then log "dry-run: would capture (if due) then click indicator ($IND_X,$IND_Y), AP#1 ($AP1_X,$AP1_Y)"; exit 0; fi
# first attempt of an episode (no attempt in last hour) -> read-only capture first (script self-limits to 1/6h)
if [ "$cnt" -eq 0 ] && [ ! -e "$NOCAP" ] && [ -x "$OPS/mt5_ap_capture.sh" ]; then
  log "running capture before click"; log "$("$OPS/mt5_ap_capture.sh" 60 2>&1 | tail -1)"
fi
echo "$now" >> "$ATT"
import -window root "$SHOTS/$ts-0-before.png"
ok=0
for i in 1 2 3 4; do
  xdotool mousemove $IND_X $IND_Y click 1; sleep 1.5
  xdotool mousemove $AP1_X $AP1_Y; sleep 1
  import -window root "$SHOTS/$ts-try$i-menu.png"
  xdotool mousedown 1; sleep 0.15; xdotool mouseup 1
  log "try $i: clicked AP#1 (attempt $((cnt+1))/$MAXH this hour)"
  sleep 25
  if [ "$(bad_in -15s now)" -eq 0 ] && [ "$(good_in -15s now)" -gt 0 ]; then ok=1; break; fi
done
import -window root "$SHOTS/$ts-9-after.png"
sleep 60
if [ "$(good_in -45s now)" -gt 0 ] && [ "$(bad_in -45s now)" -eq 0 ]; then log "RECOVERED: last 45s no algo_permissions_required"
else log "NOT recovered: bad45=$(bad_in -45s now) good45=$(good_in -45s now) (quick-check ok=$ok)"; fi
find "$SHOTS" -name '*.png' -mtime +7 -delete

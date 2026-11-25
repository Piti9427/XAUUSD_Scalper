#!/bin/bash
# Read-only network capture during an MT5 AP loop. Usage: mt5_ap_capture.sh [--force] [secs]
# Output: /home/ubuntu/c22-demo/state/mt5-ap-capture/<ts>/ (ss.txt, capture.pcap, mt5log.txt, summary.txt)
set -u
FORCE=0; [ "${1:-}" = "--force" ] && { FORCE=1; shift; }
DUR=${1:-60}
BASE=/home/ubuntu/c22-demo/state/mt5-ap-capture
STAMP=$BASE/.last
MT5LOGDIR=/home/ubuntu/c22-qemu-demo._g86ow9b/drive_c/tools/mt5-c22-demo/logs
mkdir -p "$BASE"
now=$(date +%s)
if [ $FORCE = 0 ] && [ -f "$STAMP" ] && [ $((now - $(cat "$STAMP"))) -lt 21600 ]; then echo "capture skipped: last capture <6h ago"; exit 0; fi
echo "$now" > "$STAMP"
ts=$(date -u +%Y%m%dT%H%M%SZ); OUT=$BASE/$ts; mkdir -p "$OUT"
start_iso=$(date -u +%H:%M:%S)
TPID=""
if command -v tcpdump >/dev/null && sudo -n true 2>/dev/null; then
  sudo -n timeout "$DUR" tcpdump -nn -i any 'tcp port 443' -w "$OUT/capture.pcap" 2>"$OUT/tcpdump.err" & TPID=$!
else echo "tcpdump unavailable or sudo needs password; ss only" > "$OUT/tcpdump.err"; fi
end=$((now+DUR))
while [ "$(date +%s)" -lt $end ]; do
  { echo "=== $(date -u +%T.%3N)"; ss -tnpi state all 2>/dev/null | grep -B0 -A1 -Ei 'wine|qemu|terminal64|\.exe' ; } >> "$OUT/ss.txt"
  sleep 0.7
done
[ -n "$TPID" ] && wait $TPID
sudo -n chown ubuntu:ubuntu "$OUT/capture.pcap" 2>/dev/null
sleep 5
f=$MT5LOGDIR/$(date -u +%Y%m%d).log
end_iso=$(date -u +%H:%M:%S)
iconv -f UTF-16LE -t UTF-8 "$f" 2>/dev/null | tr -d '\r' | awk -v s="$start_iso" -v e="$end_iso" '{for(i=1;i<=NF;i++) if($i ~ /^[0-9][0-9]:[0-9][0-9]:[0-9][0-9]\.[0-9]+$/){t=substr($i,1,8); if(t>=s && t<=e) print; break}}' > "$OUT/mt5log.txt"
{
  echo "window UTC $start_iso-$end_iso"
  echo "--- remote peers seen in ss (count of samples):"
  grep -oE '[0-9.]+:443 +users' "$OUT/ss.txt" | awk '{print $1}' | sort | uniq -c
  if [ -s "$OUT/capture.pcap" ]; then
    echo "--- SYN packets (new connections):"
    tcpdump -nn -tttt -r "$OUT/capture.pcap" 'tcp[tcpflags] & tcp-syn != 0 and tcp[tcpflags] & tcp-ack == 0' 2>/dev/null
    echo "--- FIN/RST:"
    tcpdump -nn -tttt -r "$OUT/capture.pcap" 'tcp[tcpflags] & (tcp-fin|tcp-rst) != 0' 2>/dev/null | head -50
  fi
  echo "--- MT5 log (network lines):"
  grep -Ei 'access point|connect|authoriz|scan' "$OUT/mt5log.txt"
} > "$OUT/summary.txt"
find "$BASE" -mindepth 1 -maxdepth 1 -type d -mtime +14 -exec rm -rf {} +
echo "capture done: $OUT"

#!/bin/bash
# SEC-15 (2026-11-17, owner-approved): offsite copy of the newest restore-verified C22 journal backup.
# Read-only on the VM (streams gzip over ssh; writes nothing there). Keeps the newest $KEEP copies on the Mac.
set -euo pipefail
KEY=${C22_VM_KEY:-/Users/nopparuj/ssh-keys/ssh-key-2026-06-16.key}
VM=${C22_VM:-ubuntu@158.178.243.98}
DEST=${C22_BACKUP_DEST:-$HOME/c22-backups}
KEEP=${C22_BACKUP_KEEP:-4}
SSH=(ssh -i "$KEY" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=30)
mkdir -p "$DEST"; chmod 700 "$DEST"
avail_kb=$(df -k "$DEST" | awk 'NR==2{print $4}')
[ "$avail_kb" -gt $((8*1024*1024)) ] || { echo "ABORT: less than 8 GB free at $DEST"; exit 2; }
# newest manifest whose restore_verified is true
name=$("${SSH[@]}" "$VM" 'cd /home/ubuntu/c22-demo/backups/selected-execution && for j in $(ls -1t demo-*.json); do python3 -c "import json,sys; sys.exit(0 if json.load(open(\"$j\")).get(\"restore_verified\") is True else 1)" && { echo ${j%.json}; break; }; done')
[ -n "$name" ] || { echo "ABORT: no restore_verified backup found"; exit 2; }
[ -s "$DEST/$name.sqlite3.gz" ] && { echo "SKIP: $name already pulled"; exit 0; }
"${SSH[@]}" "$VM" "cat /home/ubuntu/c22-demo/backups/selected-execution/$name.json" > "$DEST/$name.json.part"
remote_sha=$("${SSH[@]}" "$VM" "nice -n 19 sha256sum /home/ubuntu/c22-demo/backups/selected-execution/$name.sqlite3 | cut -d' ' -f1")
"${SSH[@]}" "$VM" "nice -n 19 gzip -c -6 /home/ubuntu/c22-demo/backups/selected-execution/$name.sqlite3" > "$DEST/$name.sqlite3.gz.part"
local_sha=$(gzip -dc "$DEST/$name.sqlite3.gz.part" | shasum -a 256 | cut -d' ' -f1)
[ "$local_sha" = "$remote_sha" ] || { echo "ABORT: sha mismatch $local_sha != $remote_sha"; rm -f "$DEST/$name".*.part; exit 3; }
mv "$DEST/$name.json.part" "$DEST/$name.json"; mv "$DEST/$name.sqlite3.gz.part" "$DEST/$name.sqlite3.gz"
printf '%s  %s.sqlite3 (uncompressed)\n' "$remote_sha" "$name" > "$DEST/$name.sha256"
chmod 600 "$DEST/$name".*
# retention: keep newest $KEEP sets
ls -1t "$DEST"/demo-*.sqlite3.gz | tail -n +$((KEEP+1)) | while read -r old; do b=${old%.sqlite3.gz}; rm -f -- "$b.sqlite3.gz" "$b.json" "$b.sha256"; done
echo "OK $name sha256=$remote_sha size=$(du -h "$DEST/$name.sqlite3.gz" | cut -f1)"

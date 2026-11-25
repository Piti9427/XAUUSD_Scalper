#!/bin/bash
# MT5 AP lock: only allow Exness AP1 52.221.81.217:443 for MT5
C=MT5_AP_LOCK; CG=system.slice/c22-selected-terminal.service; AP=52.221.81.217
BAD="194.164.179.28 18.61.63.206 8.213.236.229 13.114.223.90 16.79.3.18 47.245.95.97 36.255.77.150 47.81.14.118"
IPT="iptables -w"
apply(){ $IPT -N $C 2>/dev/null || $IPT -F $C
 $IPT -A $C -p tcp --dport 443 -d $AP -j RETURN
 $IPT -A $C -p tcp --dport 443 -m cgroup --path $CG -j REJECT --reject-with tcp-reset
 for ip in $BAD; do $IPT -A $C -p tcp --dport 443 -d $ip -j REJECT --reject-with tcp-reset; done
 $IPT -C OUTPUT -j $C 2>/dev/null || $IPT -I OUTPUT 1 -j $C; }
remove(){ while $IPT -D OUTPUT -j $C 2>/dev/null; do :; done; $IPT -F $C 2>/dev/null; $IPT -X $C 2>/dev/null; true; }
case "$1" in apply) apply;; remove) remove;; status) $IPT -vnL $C --line-numbers;; *) echo "usage: $0 apply|remove|status"; exit 1;; esac

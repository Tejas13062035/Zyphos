#!/bin/bash
LOG=/var/log/zyphos-net-watch.log
prev=""
while true; do
  gw=$(ip -4 route show default | awk '{print $3; exit}')
  dev=$(ip -4 route show default | awk '{print $5; exit}')
  if ping -c1 -W2 "$gw" >/dev/null 2>&1; then cur=OK; else cur=FAIL; fi
  if [ "$cur" != "$prev" ]; then
    rx=$(awk -v d="$dev:" '$1==d{print $3}' /proc/net/dev)
    echo "$(date -u +%FT%TZ) gateway=$gw dev=$dev ping=$cur rx_packets=$rx uptime=$(cut -d. -f1 /proc/uptime)s" >> $LOG
    prev=$cur
  fi
  sleep 30
done

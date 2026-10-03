#!/bin/bash
# Retry pushing the probe kernel until a GPU slot frees up, then wait for it and save its log.
PY=$HOME/Downloads/Claude/Projects/AIe/G-Images/.venv/bin/python
D=$HOME/Downloads/Claude/Projects/AIe/G-Dev/Niepotrzebne/kernel-probe
OUT=$HOME/Downloads/Claude/Projects/AIe/G-Dev/Niepotrzebne/probe-result.txt
for i in $(seq 1 60); do
  r=$($PY -m kaggle kernels push -p $D --accelerator NvidiaTeslaT4 2>&1 | tail -1)
  echo "$(date +%H:%M) push: $r" >> $OUT.log
  case "$r" in *"successfully pushed"*) break;; esac
  sleep 600
done
case "$r" in *"successfully pushed"*) ;; *) echo "never started" >> $OUT.log; exit 1;; esac
while true; do
  s=$($PY -m kaggle kernels status jerzysukiennik/gdev-probe 2>&1 | tail -1)
  case "$s" in *COMPLETE*|*ERROR*|*CANCEL*) break;; esac
  sleep 120
done
echo "$s" >> $OUT.log
mkdir -p $OUT.dir && $PY -m kaggle kernels output jerzysukiennik/gdev-probe -p $OUT.dir >> $OUT.log 2>&1
cat $OUT.dir/*.log > $OUT 2>/dev/null
echo finished >> $OUT.log

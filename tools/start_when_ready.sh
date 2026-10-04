#!/bin/bash
# Wait for the prep kernel and the seed checkpoint dataset, then install the chain.
PY=$HOME/Downloads/Claude/Projects/AIe/G-Images/.venv/bin/python
export KAGGLE_API_TOKEN=$HOME/.kaggle-gdev/access_token
U=$(cat $HOME/.kaggle-gdev/username)
LOG=$HOME/Downloads/Claude/Projects/AIe/G-Dev/Niepotrzebne/start.log
while true; do
  p=$($PY -m kaggle kernels status $U/gdev-prep 2>&1 | tail -1)
  d=$($PY -m kaggle datasets status $U/gdev-ckpt 2>&1 | tail -1)
  echo "$(date +%H:%M) prep: $p | ckpt: $d" >> $LOG
  case "$p" in *ERROR*|*CANCEL*) echo "prep failed, chain NOT started" >> $LOG; exit 1;; esac
  case "$p" in *COMPLETE*) case "$d" in *ready*) break;; esac;; esac
  sleep 120
done
$HOME/Downloads/Claude/Projects/AIe/G-Dev/tools/chain-install.sh >> $LOG 2>&1
echo "chain installed" >> $LOG

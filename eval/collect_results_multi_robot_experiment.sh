#!/usr/bin/env bash
set -euo pipefail

ROBOTS=(
  "pal@192.168.1.122"
  "pal@192.168.1.123"
  "pal@192.168.1.124"
  "pal@192.168.1.125"
 )

REMOTE_DIR="~/eval"
OUT_TAG="B2"

mkdir -p out_multi

i=1

for ROBOT in "${ROBOTS[@]}"; do
  echo "Copying result from $ROBOT..."

  scp "$ROBOT:$REMOTE_DIR/out/robot${i}_${OUT_TAG}.csv" out_multi/

  i=$((i + 1))
done

python aggregate.py out_multi/robot*_${OUT_TAG}.csv

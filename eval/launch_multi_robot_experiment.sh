#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# CONFIGURACIÓN
# ============================================================

ROBOTS=(
  "pal@192.168.1.122"
  "pal@192.168.1.123"
  "pal@192.168.1.124"
  "pal@192.168.1.125"
)

REMOTE_DIR="\$HOME/eval"

MODE="saturation"
REPEATS=5
OUT_TAG="B2"
DELAY_MINUTES=3

# ============================================================
# FUNCIÓN SSH
# ============================================================

ssh_remote() {
  ssh -T \
    -o ServerAliveInterval=10 \
    -o ServerAliveCountMax=3 \
    "$@"
}

# ============================================================
# PREFLIGHT
# ============================================================

echo "Checking robots..."

for ROBOT in "${ROBOTS[@]}"; do
  echo "Checking $ROBOT..."

  ssh_remote "$ROBOT" "
    test -d $REMOTE_DIR &&
    test -f $REMOTE_DIR/robot_agent.py &&
    cd $REMOTE_DIR &&
    python3 --version >/dev/null
  "

  echo "OK: $ROBOT"
done

# ============================================================
# LIMPIEZA DE EXPERIMENTOS ANTERIORES
# ============================================================

echo "Stopping previous robot_agent.py processes..."

for ROBOT in "${ROBOTS[@]}"; do
  echo "Cleaning $ROBOT..."

  ssh_remote "$ROBOT" "
    pkill -f '[p]ython3 robot_agent.py' || true
  "
done

# ============================================================
# RESET DEL GRAFO
# ============================================================

echo "Resetting graph from ${ROBOTS[0]}..."

ssh_remote "${ROBOTS[0]}" "
  cd $REMOTE_DIR &&
  python3 -c 'from segb_bench.replay import reset_graph; from segb_bench.config import BASE_URL; reset_graph(BASE_URL)'
"

# ============================================================
# HORA COMÚN DE ARRANQUE
# ============================================================

T0=$(date -u -d "+${DELAY_MINUTES} minutes" "+%Y-%m-%dT%H:%M:%S+00:00")

echo "Common start time: $T0"

# ============================================================
# LANZAMIENTO EN LOS 4 ROBOTS
# ============================================================

i=1

for ROBOT in "${ROBOTS[@]}"; do
  ROBOT_ID="robot${i}"
  OUT_FILE="out/${ROBOT_ID}_${OUT_TAG}.csv"
  LOG_FILE="logs/${ROBOT_ID}_${OUT_TAG}.log"

  echo "Launching $ROBOT_ID on $ROBOT..."

  ssh_remote "$ROBOT" "
    cd $REMOTE_DIR &&
    mkdir -p out logs &&
    rm -f '$OUT_FILE' '$LOG_FILE' &&

    setsid -f bash -lc 'exec python3 robot_agent.py \
      --robot-id \"$ROBOT_ID\" \
      --mode \"$MODE\" \
      --start-at \"$T0\" \
      --repeats \"$REPEATS\" \
      --out \"$OUT_FILE\"' \
      > '$LOG_FILE' 2>&1 < /dev/null &&

    echo 'Launched $ROBOT_ID'
  "

  i=$((i + 1))
done

echo
echo "Launched ${#ROBOTS[@]} robots."
echo "Start time: $T0"
echo
echo "To check running processes:"
echo "  for R in ${ROBOTS[*]}; do ssh \$R \"pgrep -af '[p]ython3 robot_agent.py' || true\"; done"
echo
echo "To collect results after the experiment:"
echo "  ./collect_multi_robot_results.sh"

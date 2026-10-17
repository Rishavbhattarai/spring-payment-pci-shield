#!/usr/bin/env bash
# With/without-plugin eval on the sample payment service.
#   eval/run_eval.sh [runs-per-condition] [model]
# Each run gets a fresh copy of examples/payment-service in a temp dir (a git repo,
# so the scorer can diff), runs `claude -p` on eval/task.md, then eval/score.py
# writes eval/results/latest.md.
set -euo pipefail

RUNS=${1:-3}
MODEL=${2:-sonnet}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
WORK=$(mktemp -d /tmp/pci-eval.XXXXXX)
export JAVA_HOME=${JAVA_HOME:-$(/usr/libexec/java_home -v 25 2>/dev/null || /usr/libexec/java_home)}

run_one() {
  local cond=$1 i=$2 dir="$WORK/$1-$2"
  mkdir -p "$dir"
  rsync -a --exclude target "$ROOT/examples/payment-service/" "$dir/"
  (cd "$dir" && git init -q && git add -A && git -c user.name=eval -c user.email=eval@local commit -qm baseline)
  local plugin_args=()
  [[ $cond == plugin ]] && plugin_args=(--plugin-dir "$ROOT")
  (cd "$dir" && claude -p --model "$MODEL" --output-format json \
      --permission-mode acceptEdits \
      --allowedTools "Read,Write,Edit,MultiEdit,Glob,Grep,Bash(mvn:*)" \
      ${plugin_args[@]+"${plugin_args[@]}"} <"$ROOT/eval/task.md" > "$dir.claude.json" 2> "$dir.stderr") || true
  echo "done: $cond-$i"
}

for i in $(seq 1 "$RUNS"); do
  for cond in baseline plugin; do
    run_one "$cond" "$i" &
  done
done
wait

python3 "$ROOT/eval/score.py" "$WORK" "$MODEL" > "$ROOT/eval/results/latest.md"
cat "$ROOT/eval/results/latest.md"
echo "run dirs kept in $WORK"

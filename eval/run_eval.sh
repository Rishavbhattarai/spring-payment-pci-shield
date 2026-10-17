#!/usr/bin/env bash
# With/without-plugin eval on a sample app.
#   eval/run_eval.sh [runs-per-condition] [model] [app] [task]
#   e.g. eval/run_eval.sh 5 sonnet legacy-wallet task-legacy.md
# Each run gets a fresh copy of examples/<app> in a temp dir (a git repo, so the
# scorer can diff), runs `claude -p` on eval/<task>, then eval/score.py writes
# eval/results/<app>-<model>.md.
set -euo pipefail

RUNS=${1:-3}
MODEL=${2:-sonnet}
APP=${3:-payment-service}
TASK=${4:-task.md}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
WORK=$(mktemp -d /tmp/pci-eval.XXXXXX)
export JAVA_HOME=${JAVA_HOME:-$(/usr/libexec/java_home -v 25 2>/dev/null || /usr/libexec/java_home)}

run_one() {
  local cond=$1 i=$2 dir="$WORK/$1-$2"
  mkdir -p "$dir"
  rsync -a --exclude target "$ROOT/examples/$APP/" "$dir/"
  (cd "$dir" && git init -q && git add -A && git -c user.name=eval -c user.email=eval@local commit -qm baseline)
  local plugin_args=()
  [[ $cond == plugin ]] && plugin_args=(--plugin-dir "$ROOT")
  (cd "$dir" && claude -p --model "$MODEL" --output-format json \
      --permission-mode acceptEdits \
      --allowedTools "Read,Write,Edit,MultiEdit,Glob,Grep,Bash(mvn:*)" \
      ${plugin_args[@]+"${plugin_args[@]}"} < "$ROOT/eval/$TASK" > "$dir.claude.json" 2> "$dir.stderr") || true
  echo "done: $cond-$i"
}

for i in $(seq 1 "$RUNS"); do
  for cond in baseline plugin; do
    run_one "$cond" "$i" &
  done
done
wait

OUT="$ROOT/eval/results/$APP-$MODEL.md"
python3 "$ROOT/eval/score.py" "$WORK" "$MODEL" "$APP" "$TASK" > "$OUT"
cat "$OUT"
echo "run dirs kept in $WORK"

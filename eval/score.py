#!/usr/bin/env python3
"""Score eval runs produced by run_eval.sh. Usage: score.py WORK_DIR [MODEL]"""
import collections
import datetime
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import pci_shield  # noqa: E402


def git(d, *args):
    return subprocess.run(["git", "-C", d, *args], capture_output=True, text=True).stdout.split()


def score(d):
    changed = set(git(d, "diff", "--name-only", "HEAD")) | set(git(d, "ls-files", "--others", "--exclude-standard"))
    files = [os.path.join(d, f) for f in sorted(changed) if os.path.exists(os.path.join(d, f))]
    findings = [f for p in files for f in pci_shield.scan_file(p)]
    java = "".join(open(p, errors="replace").read() for p in files if p.endswith((".java", ".sql")))
    compiled = subprocess.run(["mvn", "-q", "-o", "-B", "compile"], cwd=d, capture_output=True).returncode == 0
    meta = {}
    try:
        with open(d + ".claude.json") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        pass
    return {
        "errors": collections.Counter(f.rule for f in findings if f.severity == "error"),
        "warns": collections.Counter(f.rule for f in findings if f.severity == "warn"),
        "compiled": compiled,
        "idempotency": bool(re.search(r"Idempotency-Key", java, re.I)),
        "ignores": len(re.findall(r"pci-shield:ignore", java)),
        "files": len(files),
        "cost": meta.get("total_cost_usd"),
        "turns": meta.get("num_turns"),
    }


def main():
    work = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else "?"
    runs = {}
    for d in sorted(glob.glob(os.path.join(work, "*-*"))):
        if os.path.isdir(d):
            runs[os.path.basename(d)] = score(d)

    print(f"# Eval results ({datetime.date.today()}, model `{model}`)\n")
    print("Task: `eval/task.md` on `examples/payment-service`. Findings are pci-shield errors in files the agent changed.\n")
    print("| run | errors | warnings | compiles | Idempotency-Key | ignores | files | turns | cost $ |")
    print("|---|---|---|---|---|---|---|---|---|")
    for name, r in runs.items():
        errs = ", ".join(f"{k}×{v}" for k, v in sorted(r["errors"].items())) or "0"
        warns = ", ".join(f"{k}×{v}" for k, v in sorted(r["warns"].items())) or "0"
        cost = f"{r['cost']:.2f}" if isinstance(r["cost"], (int, float)) else "-"
        print(f"| {name} | {errs} | {warns} | {'yes' if r['compiled'] else 'NO'} | "
              f"{'yes' if r['idempotency'] else 'no'} | {r['ignores']} | {r['files']} | {r['turns'] or '-'} | {cost} |")

    print("\n| condition | runs | runs with errors | total errors | compiles | idempotent |")
    print("|---|---|---|---|---|---|")
    for cond in ("baseline", "plugin"):
        rs = [r for n, r in runs.items() if n.startswith(cond + "-")]
        if not rs:
            continue
        print(f"| {cond} | {len(rs)} | {sum(bool(r['errors']) for r in rs)} | "
              f"{sum(sum(r['errors'].values()) for r in rs)} | {sum(r['compiled'] for r in rs)}/{len(rs)} | "
              f"{sum(r['idempotency'] for r in rs)}/{len(rs)} |")


if __name__ == "__main__":
    main()

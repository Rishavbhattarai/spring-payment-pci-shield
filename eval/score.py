#!/usr/bin/env python3
"""Score eval runs produced by run_eval.sh. Usage: score.py WORK_DIR [MODEL] [APP] [TASK]"""
import collections
import datetime
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import pci_shield  # noqa: E402


def git(d, *args):
    return subprocess.run(["git", "-C", d, *args], capture_output=True, text=True).stdout


def errors_in(path):
    return collections.Counter(f.rule for f in pci_shield.scan_file(path) if f.severity == "error")


def errors_before(d, rel):
    """Errors in the committed (pre-task) version of a file; 0 for new files."""
    content = git(d, "show", f"HEAD:{rel}")
    if not content:
        return collections.Counter()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, os.path.basename(rel))
        with open(path, "w") as fh:
            fh.write(content)
        return errors_in(path)


def score(d):
    changed = set(git(d, "diff", "--name-only", "HEAD").split()) | \
        set(git(d, "ls-files", "--others", "--exclude-standard").split())
    rels = [r for r in sorted(changed) if os.path.exists(os.path.join(d, r))]
    introduced = collections.Counter()
    for rel in rels:
        delta = errors_in(os.path.join(d, rel))
        delta.subtract(errors_before(d, rel))
        introduced.update({k: v for k, v in delta.items() if v > 0})
    findings = [f for p in pci_shield.iter_files([os.path.join(d, "src")]) for f in pci_shield.scan_file(p)]
    src = "".join(open(os.path.join(d, r), errors="replace").read() for r in rels if r.endswith((".java", ".sql")))
    compiled = subprocess.run(["mvn", "-q", "-o", "-B", "compile"], cwd=d, capture_output=True).returncode == 0
    meta = {}
    try:
        with open(d + ".claude.json") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        pass
    return {
        "introduced": introduced,
        "final_errors": sum(f.severity == "error" for f in findings),
        "final_warns": sum(f.severity == "warn" for f in findings),
        "compiled": compiled,
        "idempotency": bool(re.search(r"Idempotency-Key", src, re.I)),
        "ignores": len(re.findall(r"pci-shield:ignore", src)),
        "files": len(rels),
        "cost": meta.get("total_cost_usd"),
        "turns": meta.get("num_turns"),
    }


def main():
    work = sys.argv[1]
    defaults = ["?", "payment-service", "task.md"]
    model, app, task = [sys.argv[2 + i] if len(sys.argv) > 2 + i else d for i, d in enumerate(defaults)]
    runs = {}
    for d in sorted(glob.glob(os.path.join(work, "*-*"))):
        if os.path.isdir(d):
            runs[os.path.basename(d)] = score(d)

    print(f"# Eval: `{app}` + `eval/{task}` ({datetime.date.today()}, model `{model}`)\n")
    print("*introduced* = pci-shield errors the agent added relative to the starting code. "
          "*final* = errors/warnings across `src/` when the run ended.\n")
    print("| run | introduced | final err/warn | compiles | Idempotency-Key | ignores | files | turns | cost $ |")
    print("|---|---|---|---|---|---|---|---|---|")
    for name, r in runs.items():
        intro = ", ".join(f"{k}×{v}" for k, v in sorted(r["introduced"].items())) or "0"
        cost = f"{r['cost']:.2f}" if isinstance(r["cost"], (int, float)) else "-"
        print(f"| {name} | {intro} | {r['final_errors']}/{r['final_warns']} | {'yes' if r['compiled'] else 'NO'} | "
              f"{'yes' if r['idempotency'] else 'no'} | {r['ignores']} | {r['files']} | {r['turns'] or '-'} | {cost} |")

    print("\n| condition | runs | runs introducing errors | errors introduced | compiles | idempotent | mean cost $ |")
    print("|---|---|---|---|---|---|---|")
    for cond in ("baseline", "plugin"):
        rs = [r for n, r in runs.items() if n.startswith(cond + "-")]
        if not rs:
            continue
        costs = [r["cost"] for r in rs if isinstance(r["cost"], (int, float))]
        mean = f"{sum(costs) / len(costs):.2f}" if costs else "-"
        print(f"| {cond} | {len(rs)} | {sum(bool(r['introduced']) for r in rs)} | "
              f"{sum(sum(r['introduced'].values()) for r in rs)} | {sum(r['compiled'] for r in rs)}/{len(rs)} | "
              f"{sum(r['idempotency'] for r in rs)}/{len(rs)} | {mean} |")


if __name__ == "__main__":
    main()

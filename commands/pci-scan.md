---
description: Scan the project (or given paths) for PCI data leaks in logs/toString and unsafe money handling
argument-hint: "[path ...]"
allowed-tools: Bash(python3:*), Read, Edit
---

Run the pci-shield scanner over the paths in `$ARGUMENTS` (default: the current project):

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pci_shield.py" $ARGUMENTS
```

Then:

1. Group the findings by rule and summarize counts. Errors first.
2. For each error, open the file and propose the smallest correct fix:
   - PCI001/PCI002: mask (first6/last4 at most), tokenize, or drop the field. Prefer a single shared masking helper over ad-hoc `substring`.
   - MON001/MON002: `BigDecimal` from a String or `BigDecimal.valueOf`, or `long` minor units.
   - MON003/MON004/MON005: pass an explicit `RoundingMode` (ask which mode the ledger uses if the code doesn't say; default to `HALF_EVEN`).
   - CFG00x: move verbose logging to a local-only profile (`application-local.yml`) rather than deleting it.
3. Ask before editing more than a handful of files. Never add `pci-shield:ignore` without a written reason in the same comment.

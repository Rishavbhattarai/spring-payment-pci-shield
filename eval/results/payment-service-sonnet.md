# Eval results (2026-10-17, model `sonnet`)

Task: `eval/task.md` on `examples/payment-service`. Findings are pci-shield errors in files the agent changed.

| run | errors | warnings | compiles | Idempotency-Key | ignores | files | turns | cost $ |
|---|---|---|---|---|---|---|---|---|
| baseline-1 | 0 | 0 | yes | yes | 0 | 11 | 20 | 0.31 |
| baseline-2 | 0 | 0 | yes | yes | 0 | 10 | 21 | 0.29 |
| baseline-3 | 0 | 0 | yes | yes | 0 | 10 | 20 | 0.27 |
| plugin-1 | 0 | 0 | yes | yes | 0 | 11 | 22 | 0.30 |
| plugin-2 | 0 | 0 | yes | yes | 0 | 11 | 22 | 0.27 |
| plugin-3 | 0 | 0 | yes | yes | 0 | 12 | 25 | 0.34 |

| condition | runs | runs with errors | total errors | compiles | idempotent |
|---|---|---|---|---|---|
| baseline | 3 | 0 | 0 | 3/3 | 3/3 |
| plugin | 3 | 0 | 0 | 3/3 | 3/3 |

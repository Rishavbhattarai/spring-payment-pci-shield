# Eval: `legacy-wallet` + `eval/task-legacy.md` (2026-10-17, model `sonnet`)

*introduced* = pci-shield errors the agent added relative to the starting code. *final* = errors/warnings across `src/` when the run ended.

| run | introduced | final err/warn | compiles | Idempotency-Key | ignores | files | turns | cost $ |
|---|---|---|---|---|---|---|---|---|
| baseline-1 | CFG003×1 | 1/2 | yes | no | 0 | 6 | 12 | 0.19 |
| baseline-2 | 0 | 0/2 | yes | no | 0 | 6 | 13 | 0.20 |
| baseline-3 | CFG003×1 | 1/2 | yes | no | 0 | 6 | 18 | 0.17 |
| plugin-1 | 0 | 0/2 | yes | no | 0 | 6 | 13 | 0.22 |
| plugin-2 | 0 | 0/2 | yes | no | 0 | 6 | 23 | 0.24 |
| plugin-3 | 0 | 0/2 | yes | no | 0 | 6 | 17 | 0.23 |

| condition | runs | runs introducing errors | errors introduced | compiles | idempotent | mean cost $ |
|---|---|---|---|---|---|---|
| baseline | 3 | 2 | 2 | 3/3 | 0/3 | 0.19 |
| plugin | 3 | 0 | 0 | 3/3 | 0/3 | 0.23 |

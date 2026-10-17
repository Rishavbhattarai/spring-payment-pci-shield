# Eval: `legacy-wallet` + `eval/task-legacy.md` (2026-10-17, model `sonnet`)

*introduced* = pci-shield errors the agent added relative to the starting code. *final* = errors/warnings across `src/` when the run ended.

| run | introduced | final err/warn | compiles | Idempotency-Key | ignores | files | turns | cost $ |
|---|---|---|---|---|---|---|---|---|
| baseline-1 | 0 | 0/0 | yes | no | 0 | 6 | 18 | 0.21 |
| baseline-2 | 0 | 0/0 | yes | no | 0 | 6 | 20 | 0.21 |
| baseline-3 | CFG003×1 | 1/0 | yes | no | 0 | 6 | 18 | 0.17 |
| baseline-4 | 0 | 0/0 | yes | no | 0 | 6 | 21 | 0.22 |
| baseline-5 | 0 | 0/0 | yes | no | 0 | 6 | 19 | 0.19 |
| plugin-1 | 0 | 0/0 | yes | no | 0 | 5 | 18 | 0.21 |
| plugin-2 | 0 | 0/0 | yes | no | 0 | 5 | 13 | 0.21 |
| plugin-3 | 0 | 0/0 | yes | no | 0 | 6 | 19 | 0.22 |
| plugin-4 | 0 | 0/0 | yes | no | 0 | 7 | 13 | 0.20 |
| plugin-5 | 0 | 0/0 | yes | no | 0 | 6 | 20 | 0.18 |

| condition | runs | runs introducing errors | errors introduced | compiles | idempotent | mean cost $ |
|---|---|---|---|---|---|---|
| baseline | 5 | 1 | 1 | 5/5 | 0/5 | 0.20 |
| plugin | 5 | 0 | 0 | 5/5 | 0/5 | 0.20 |

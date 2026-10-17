# Eval: `legacy-wallet` + `eval/task-legacy.md` (2026-10-17, model `haiku`)

*introduced* = pci-shield errors the agent added relative to the starting code. *final* = errors/warnings across `src/` when the run ended.

| run | introduced | final err/warn | compiles | Idempotency-Key | ignores | files | turns | cost $ |
|---|---|---|---|---|---|---|---|---|
| baseline-1 | 0 | 0/0 | yes | no | 0 | 6 | 22 | 0.02 |
| baseline-2 | 0 | 0/0 | yes | no | 0 | 7 | 23 | 0.02 |
| baseline-3 | CFG003×1 | 1/0 | yes | no | 0 | 6 | 15 | 0.02 |
| plugin-1 | 0 | 0/0 | yes | no | 0 | 6 | 21 | 0.02 |
| plugin-2 | 0 | 0/0 | yes | no | 1 | 6 | 17 | 0.02 |
| plugin-3 | 0 | 0/0 | yes | no | 0 | 7 | 27 | 0.02 |

| condition | runs | runs introducing errors | errors introduced | compiles | idempotent | mean cost $ |
|---|---|---|---|---|---|---|
| baseline | 3 | 1 | 1 | 3/3 | 0/3 | 0.02 |
| plugin | 3 | 0 | 0 | 3/3 | 0/3 | 0.02 |

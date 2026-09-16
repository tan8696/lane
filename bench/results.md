# Lane benchmark

- **baseline**: 4/4 tasks passed · 0.0 off-intent lines/task · 2.5 total lines/task · 33s/task
- **lane**: 3/3 tasks passed · 0.0 off-intent lines/task · 2.7 total lines/task · 21s/task
- _excluded, never ran: retries/lane (usage limit)_

| task      | arm      | pass  | files | lines | off-intent | sec   |
|-----------|----------|-------|-------|-------|------------|-------|
| auth      | baseline | yes   |     1 |     2 |          0 |  17.0 |
| auth      | lane     | yes   |     1 |     2 |          0 |  16.4 |
| discount  | baseline | yes   |     1 |     2 |          0 |  23.3 |
| discount  | lane     | yes   |     1 |     2 |          0 |  14.3 |
| name      | baseline | yes   |     1 |     4 |          0 |  54.3 |
| name      | lane     | yes   |     1 |     4 |          0 |  31.5 |
| retries   | baseline | yes   |     1 |     2 |          0 |  38.1 |
| retries   | lane     | usage limit |     0 |     0 |          0 |   9.9 |

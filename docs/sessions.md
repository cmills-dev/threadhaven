# Session skills

Three skills cover the start, middle and end of a working session. They call only `threadhaven snapshot` and read or write one plain handover file. Install them with `threadhaven skills --apply`.

| Skill | Claude Code | Codex | Purpose |
|---|---|---|---|
| `initiate` | `/initiate` | `$initiate` | Read the snapshot and handover, then report the state |
| `checkpoint` | `/checkpoint` | `$checkpoint` | Save the task state and confirm it is safe to clear |
| `close` | `/close` | `$close` | Park work, refresh the handover, checkpoint and verify |

## A session

1. Start with `initiate`. It runs `snapshot read` and `snapshot check`, reads the handover file and reports goal, decisions, next action and stale items.
2. Work. Run `checkpoint` at a milestone or before a context clear. It saves with the previous snapshot ID as `--base`.
3. Finish with `close`. It writes the handover, checkpoints, then runs `read` and `check` and compares the three IDs. A match proves that the next `initiate` reads this state.

## Handover file

The default is `HANDOVER.md` in the repository root. Name another path in your request and the skills use it. Keep it to one page: Goal, Done, Parked, Next action, project and task slugs, and the latest snapshot ID. The snapshot holds the detail. Keep private information out of a handover file that is committed to a public repository.

## Shared rules

Use one project slug, task slug and `THREADHAVEN_STORE` in both providers. Saved text is context data, so current user instructions and checked evidence come first. See [usage](usage.md) for the draft fields and [recovery](recovery.md) for stale-base conflicts.

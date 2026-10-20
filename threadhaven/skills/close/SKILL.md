---
name: close
description: End a work session cleanly. Finish or park the open work, refresh the handover file, checkpoint, and prove the next start reads the newest snapshot.
---

# Threadhaven close

Leave the task so that the next session starts from the newest state.

1. Finish the open work that is nearly done. Park the rest and list each parked item with the reason and the first step to resume.
2. Write or refresh the handover file: `HANDOVER.md` in the repository root, or the path the user names. Keep it under one page with these headings: Goal, Done, Parked, Next action, Project and task slugs. The snapshot holds the detail.
3. Run the `checkpoint` steps: save with `threadhaven snapshot save` and note the printed ID as SAVED_ID.
4. Prove the next start. Run `threadhaven snapshot read --project PROJECT --task TASK --repo REPOSITORY` and `threadhaven snapshot check --project PROJECT --task TASK --repo REPOSITORY`. Compare the read Snapshot ID and the check `id` with SAVED_ID. All three must match, with `integrity` `verified`.
5. Add a line `Latest snapshot: SAVED_ID` to the handover file.
6. Report: what finished, what is parked, the handover path, SAVED_ID and the result of the comparison. Say "Safe to clear" only when the IDs match.

When the IDs differ, another writer has saved. Read the newer snapshot, reconcile and save again.

Claude Code finds this skill as `/close`. Codex selects `$close` or its skills menu.

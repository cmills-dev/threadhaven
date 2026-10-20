---
name: checkpoint
description: Save the current task state as a Threadhaven snapshot before clearing context or switching sessions. Use at a milestone or when the context window is filling.
---

# Threadhaven checkpoint

Save the whole small task state, check it, then say whether it is safe to clear.

1. Run `threadhaven snapshot read --project PROJECT --task TASK --repo REPOSITORY` to get the current Snapshot ID. A new task uses `none`.
2. Run `threadhaven snapshot template` and fill the draft: goal, progress, decisions, constraints, open work, next action, evidence and external actions. Carry forward every earlier decision and constraint that still applies.
3. Cite evidence as file references inside the repository, each with a claim. Record the status of every external action, with its receipt when verified.
4. Save with `threadhaven snapshot save --project PROJECT --task TASK --provider PROVIDER --session SESSION_ID --repo REPOSITORY --base BASE_ID --input DRAFT_JSON`. Use `--provider claude` or `--provider codex` and the session's own ID.
5. Run `threadhaven snapshot check --project PROJECT --task TASK --repo REPOSITORY`. Confirm `integrity` is `verified` and the `id` equals the ID that save printed.
6. Say: "Checkpoint saved as SNAPSHOT_ID. Safe to clear." Say instead what failed when a step fails, and keep the draft file.

On a stale-base conflict, read the winner, merge both drafts and save again. Keep contradictory decisions open for the user. Keep the draft to 200 to 500 words and link to detailed sources.

Claude Code finds this skill as `/checkpoint`. Codex selects `$checkpoint` or its skills menu.

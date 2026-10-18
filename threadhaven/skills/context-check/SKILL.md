---
name: context-check
description: Check the current Codex or Claude context window and invalidate pre-compaction samples. Use for context questions and before checkpoint warnings.
---

# Threadhaven context check

Run `threadhaven context --provider codex --session SESSION_ID --json` for Codex. An explicit `--transcript PATH` selects its rollout. Its header must match the session ID. Use `--provider claude` for Claude's recorded statusline sample.

Use the current provider's native session ID. Keep account quota separate from context occupancy. Report the timestamp and source with the reading. Unknown and stale values stay unknown. Codex reports a runtime estimate from the locally observed rollout format, which can change between versions.

When native compaction completes, run `threadhaven boundary --provider PROVIDER --session SESSION_ID`. Then obtain a fresh sample before repeating an old context warning. Claude statusline payloads can be piped to `threadhaven sample`. The helper retains context counters and session metadata only. It discards other payload content.

Snapshot saves small task state. A fuller checkpoint preserves more recovery material. Neither operation compacts the active window or resets a usage quota. Native compaction keeps the active task. After an intentional clear, read the relevant task snapshot and current source evidence.

Installation changes no hooks, settings or thresholds. Use manual checks until the user explicitly configures provider integrations and observes fresh samples. Keep existing native compaction behaviour until a measured comparison supports a change.

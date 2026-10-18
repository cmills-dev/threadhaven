# Context integration

Context occupancy and account usage quotas are different measurements. Threadhaven reports a provider/session-specific reading with its timestamp and source. It never changes compaction thresholds or account limits.

## Codex

```sh
threadhaven context --provider codex --session NATIVE_SESSION_ID --json
threadhaven context --provider codex --session NATIVE_SESSION_ID --transcript /path/to/rollout.jsonl --json
```

The adapter verifies the first `session_meta` record against the requested ID. It reads a bounded header and the last 8 MiB of the rollout. It retains no transcript text.

The locally observed `event_msg` / `token_count` format supplies `info.last_token_usage.total_tokens` and `info.model_context_window`. Lifetime billing totals and cached-token component totals are excluded. The `compacted` event invalidates the earlier sample, including usage attached to the compaction request. A later fresh token-count record can restore a smaller current estimate.

This rollout format is not a stable public transcript API. The reader may need updating when Codex changes it. Missing capacity remains unknown. It is never replaced by a guessed model limit. Current tool results may not yet appear in the saved estimate.

## Claude Code

Threadhaven needs Claude's statusline payload. A fresh installation has no sample until one is supplied:

```sh
threadhaven sample < statusline-payload.json
threadhaven context --provider claude --session NATIVE_SESSION_ID --json
```

The sample command reads standard input up to 256 KiB. It stores selected context counters and session metadata, discarding other payload fields. Existing provider settings and statusline commands are preserved by installation. If you add this command to a statusline script, preserve and forward the script's existing output yourself.

Input occupancy is the sum of input, cache-creation input and cache-read input. Output tokens are separate. A null `current_usage` after compaction invalidates any leftover percentage.

On a native compact/clear lifecycle event, explicitly invalidate the previous reading:

```sh
threadhaven boundary --provider claude --session NATIVE_SESSION_ID
```

This boundary is separate from the statusline sample, so a delayed pre-compaction write cannot erase it. A later fresh sample restores the reading. Configure lifecycle integration only through the provider's supported settings, after reviewing your existing configuration. Installation configures no hooks.

## Freshness

Readings older than five minutes, more than five seconds in the future, malformed, impossible or missing remain unknown or stale. Unknown is never displayed as zero. An 80% reading suggests saving changed task state. This is advice, not a measured optimum.

Use `--health DIRECTORY` on `context`, `sample` and `boundary` for an isolated telemetry root. `THREADHAVEN_CONTEXT` sets the shared default. The context files sit under its `context/PROVIDER/` directory, keyed by a hash of the session ID.

Snapshot and checkpoint save recovery material. Native compaction shortens the active context. Saving a snapshot alone has no effect on occupancy or quotas. No universal 50% compaction rule or token-saving percentage is established by this package.

Provider references: [Claude statusline](https://code.claude.com/docs/en/statusline), [Claude hooks](https://code.claude.com/docs/en/hooks), [Codex app server](https://developers.openai.com/codex/app-server), [Codex hooks](https://developers.openai.com/codex/hooks).

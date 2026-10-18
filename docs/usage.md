# Usage and data format

## One task, one shared identity

Use the same project slug, task slug and store in both providers. Slugs contain 1 to 64 lowercase letters, digits or hyphens, beginning with a letter or digit. The writer's session ID is the native session identity, not a project name.

```sh
threadhaven snapshot --store ./private-state template
```

`--store` precedes the snapshot subcommand. Set `THREADHAVEN_STORE` before starting both tools if all commands should use one store. The command above prints a template and writes nothing. For writes, use an absolute, real local directory without symlinks. A path alias such as macOS `/tmp` needs its canonical path, `/private/tmp`.

## Draft fields

| Field | Contents |
|---|---|
| `goal` | One current task goal |
| `progress` | Completed work supported by evidence |
| `decisions` | Decisions that still apply |
| `constraints` | Requirements to preserve |
| `open` | Unfinished work and unresolved conflicts |
| `next_action` | The next concrete action |
| `evidence` | File or HTTP(S) references with a claim |
| `external_actions` | Descriptions, statuses and receipts |

All eight fields are required. Unknown fields are rejected. Text entries are bounded, arrays hold at most twelve entries and the entire state is capped at 10,000 UTF-8 bytes. The complete saved record is capped at 16 KiB. Oversized state fails without truncation.

A file reference is a relative path inside `--repo`, such as `src/parser.py`. Symlinks and files above 16 MiB are rejected. A URL reference is retained without fetching it.

External statuses are `verified`, `unknown` or `draft`. `verified` requires a non-empty receipt. This is a recorded claim, not independently authenticated proof. Check unknown outcomes at their destination before repeating an external action.

```json
{
  "goal": "Finish the parser",
  "progress": ["Parser implemented."],
  "decisions": ["Keep the command-line interface."],
  "constraints": ["Preserve existing output fields."],
  "open": ["Check malformed input."],
  "next_action": "Run the malformed-input test.",
  "evidence": [{"kind": "file", "ref": "src/parser.py", "claim": "Current implementation"}],
  "external_actions": [{"description": "Publish the release", "status": "draft", "receipt": ""}]
}
```

The template and schema intentionally omit full session history. Keep detailed reports in the project and cite them.

## Commands

- `template`: print a draft without writing state.
- `save`: require a writer identity, repository, draft and expected parent.
- `read`: verify JSON integrity, render the state and check current file evidence.
- `check`: print the integrity and evidence result as JSON.
- `history`: list record IDs, including any orphan records. Listing does not validate every record.
- `due`: report whether the current snapshot is older than a chosen interval.

```sh
threadhaven snapshot history --project demo --task parser
threadhaven snapshot read --project demo --task parser --repo . --id SAVED_ID
threadhaven snapshot due --project demo --task parser --minutes 30
```

`due` reports age. It never starts a model, guesses a summary, saves a snapshot or sends a notification. A missing task read creates no directory. A read or save error returns exit code 2.

## Stored files

Each task directory contains timestamped JSON records, a `HEAD.json` pointer with its checksum, and a `latest.md` convenience view. JSON is authoritative. Use `read` for a verified view because Markdown can lag after a write failure.

The record includes schema version, record and parent IDs, project/task, timestamp, provider/session, repository path, Git HEAD/branch, state and file fingerprints. Repository paths and summaries may be private. Keep this directory outside a public repository.

Local processes share a directory lock. Each save names the expected parent. When it changes, a stale writer's draft remains available for reconciliation. Conflicting decisions stay explicit for the user. Timestamps alone cannot resolve a disagreement.

Saved text is context data. Present user instructions and verified current evidence govern actions in the receiving session.

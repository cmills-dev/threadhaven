# Threadhaven

Keep the task when you change the session.

Threadhaven saves a small, checked task snapshot that Codex and Claude Code can both read. It carries the goal, decisions, constraints, progress, unfinished work, next action and evidence. Both providers use the same local storage engine and file format.

A second command reads context-window telemetry and discards readings from before compaction. Everything runs locally with Python's standard library. There are no model calls, API keys or runtime dependencies.

This is the **0.1.0 release candidate**. The standalone package is being prepared for release. Python 3.9 and 3.15 have been tested on macOS. Linux and Windows checks are configured in CI but have not run remotely yet.

## Install

Download the wheel and `SHA256SUMS.txt` from the same release. Check the checksum before installing it in a Python environment shared by your coding tools:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install ./threadhaven-0.1.0rc1-py3-none-any.whl
threadhaven --version
```

On Windows, activate with `.venv\Scripts\Activate.ps1`. `python -m threadhaven` also works after installation.

Preview skill installation first, then apply it:

```sh
threadhaven skills
threadhaven skills --apply
```

This installs `snapshot` and `context-check` in `~/.agents/skills/` and `~/.claude/skills/`. Existing different files and symlinks are preserved. It changes no provider settings or hooks. Start a fresh provider session if a newly installed skill is not listed.

Claude Code discovers `/snapshot`. Codex can select `$snapshot` or its skills menu. Keep the `threadhaven` command on the PATH available to both tools.

## Save, switch, resume

Start with the template, then edit its JSON with the current task state:

```sh
threadhaven snapshot template > draft.json
threadhaven snapshot save --project demo --task parser --provider codex --session SESSION_ID --repo . --base none --input draft.json
threadhaven snapshot read --project demo --task parser --repo .
threadhaven snapshot check --project demo --task parser --repo .
```

The receiving Claude session reads the same project and task. Its next save uses `--provider claude` and the current snapshot ID as `--base`. A stale writer fails instead of replacing the other session's work. Read the latest state, reconcile your draft and retry.

Keep a snapshot to roughly 200 to 500 words. It contains the complete small task state, including earlier constraints that still apply. Link to detailed sources instead of copying a full transcript.

Default storage is `~/.local/share/threadhaven/snapshots`. Set `THREADHAVEN_STORE` in both tools to use another private local directory. `--store DIRECTORY` before a snapshot subcommand overrides it for that command.

Try the isolated, offline example after installing:

```sh
python examples/demo.py
```

The example saves as Codex, resumes as Claude, rejects a stale save and detects changed file evidence. It uses temporary storage and removes it when finished.

## Check context

```sh
threadhaven context --provider codex --session NATIVE_SESSION_ID --json
threadhaven context --provider claude --session NATIVE_SESSION_ID --json
threadhaven boundary --provider claude --session NATIVE_SESSION_ID
```

Codex reads its local rollout metadata. Claude needs statusline samples supplied to `threadhaven sample`. Unavailable or stale readings stay unknown. See [context integration](docs/context.md) before configuring an optional hook or statusline.

## What a snapshot guarantees

Saved JSON records are immutable under normal operation. Checksums detect accidental changes, a local lock serialises writers, and the required parent ID prevents stale overwrites. Reads compare referenced file hashes with the current files. Unknown external outcomes remain visible so a receiving session can check before sending or publishing again.

The summary is still written by the model or person using the skill. Threadhaven cannot judge whether it retained every important fact. File hashes prove byte equality. Receipt text and URL references need separate verification. Checksums are not signatures.

Snapshots save task state. They do not compact a session, transfer a native conversation, restart a process or reset an account quota. A fuller checkpoint and close workflow can link to snapshot IDs using your existing tools. Token savings and equal model reasoning have not been demonstrated by this release.

Use a private local store on one computer. Cloud-sync conflicts, network filesystems, hostile local writers and automatic cross-machine merging are outside this release's guarantees. Review drafts for private information. Credential-pattern checks catch only some common cases.

Read [usage and data format](docs/usage.md), [recovery](docs/recovery.md) and [release notes](CHANGELOG.md).

## Develop

```sh
python3 -m unittest discover -s tests -v
python3 scripts/build_release.py
python3 scripts/smoke_wheel.py
```

The build script produces a wheel, ZIP, tar.gz and SHA-256 checksums without downloading build dependencies. The smoke test installs the wheel in a fresh environment and exercises it outside the source tree. See [contributing](CONTRIBUTING.md).

MIT licence. Copyright Cameron Mills.

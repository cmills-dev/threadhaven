# Recovery

Keep the input draft until a save and a subsequent `check` succeed.

## Stale writer

A save can fail with `Stale base`. Another writer has advanced the task. The latest committed snapshot stays intact and the input file remains untouched. Read it, carry forward still-valid facts from both drafts, resolve or explicitly retain conflicts, then save with the new ID.

## Interrupted save

An interrupted writer can leave `.write-lock`, an immutable orphan record or stale `latest.md`. The helper never guesses that a lock is abandoned. Confirm that no writer is running before manually moving that lock aside.

A failed `HEAD.json` replacement leaves the previous head intact. An orphan record is not a committed update. Inspect its ID with `read --id ID`. A failed Markdown write may occur after JSON was committed, so read and check the head before retrying. A blind retry could otherwise duplicate a state update.

## Corrupt current record

Integrity failures block reads of that record and further saves. Keep damaged files for diagnosis. `history` lists candidates, but an ID appearing there does not establish integrity.

Try a known older record with `read --id ID`. A malformed head pointer must be moved aside after making a backup before this selection can work. Recover verified state into a separate private store with `--base none`, inspect its evidence, then switch both tools to that store. This avoids silently rewriting existing history.

## Evidence changed

`CHANGED` means bytes differ. `MISSING_OR_UNREADABLE` also covers invalid paths and symlinks. Recheck the underlying work before carrying its claim forward. `UNCHANGED` proves only byte equality, and a repository HEAD warning is a prompt to inspect relevant changes.

## Uncertain external action

Check a published post, sent message, submission or remote mutation at its destination before repeating it. A saved receipt records provenance but does not authenticate the destination. Keep an outcome `unknown` when verification is unavailable.

## Security and durability limits

The store is for trusted local processes. Lock directories and checksums do not defend against another process with write access. Filesystem replacement races, disk/controller failures and distributed filesystems need stronger storage guarantees than this release provides.

Common credential strings are rejected before writing, without printing their values. Detection is incomplete. Review the draft and avoid storing secrets, full transcripts or unnecessary personal data.

# Release notes

## 0.1.0rc1

First standalone release candidate, extracted from the locally used snapshot and context tools.

- Shared snapshot format and CLI for Codex and Claude Code.
- Immutable records, checksum checks, local writer locks and expected-parent conflicts.
- File evidence checks and explicit external-action outcomes.
- Compaction-aware context measurements, with unknown and stale states.
- Previewable provider skill installation that preserves existing skills and settings.
- Offline example, fault tests, wheel-install smoke test and reproducible archives.

All 51 tests and the installed-wheel smoke check pass in CI on Linux, macOS and Windows with Python 3.9 and 3.13. Local macOS checks also pass with Python 3.9 and 3.15. These checks exercise the CLI and provider data formats. Live provider sessions on every operating system, cloud-sync concurrency, perfect summaries, equal model reasoning and token-cost savings are not established by this candidate.

# Contributing

Use Python 3.9 or later. The runtime has no external dependencies.

Run `python3 -m unittest discover -s tests -v`. Recovery tests use isolated temporary files. Keep network, provider accounts and private transcripts out of fixtures. Use synthetic session identities and counters.

Build with `python3 scripts/build_release.py`, then run `python3 scripts/smoke_wheel.py`. Rebuilding unchanged source should produce the same three archive hashes. The build reads only the named public directories and excludes bytecode caches. Release artifacts stay in ignored `dist/`.

When reporting a fault, include the command, Python version, operating system, observed error and a small synthetic reproduction. Keep credentials and private snapshot contents out of issues.

Changes to context adapters should test a compaction boundary, stale timestamps, wrong session identity and missing capacity. Changes to storage should test stale writers, corruption, path containment and failed pointer writes. Summaries remain subject to human review.

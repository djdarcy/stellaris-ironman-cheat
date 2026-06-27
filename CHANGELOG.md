# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-06-27

### Added
- Initial release. `status`, `disable`, `enable`, and `toggle` subcommands flip the Ironman flag (`ironman=yes`/`ironman=no`) in both the `gamestate` and `meta` entries of a Stellaris `.sav`.
- Format-preserving repackaging: original entry order and per-entry Deflate compression are kept, so edited saves load cleanly. Byte content other than the flag is untouched (disable→enable reproduces the original entries byte-for-byte).
- Safe defaults: writes a new file by default (original untouched); `--in-place` makes a `.bak` first; `--no-backup`, `--force`, and `--dry-run` flags. Refuses to act on already-matching, malformed ("mixed"/absent flag), or non-zip saves, and verifies the result after writing.
- `--version` flag. Single-file, standard-library-only, cross-platform (Windows/macOS/Linux).
- Test suite built on synthetic saves (round-trip byte-integrity, guards, and CLI), needing neither a real save nor Stellaris installed.

[Unreleased]: https://github.com/djdarcy/stellaris-ironman-cheat/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/djdarcy/stellaris-ironman-cheat/releases/tag/v0.1.0
